"""Select the main QA set and export its independent workbook."""
import json
from pathlib import Path
from judge import request_json
from semantic import read_api_key
from output_plans import qa_sheets, sheet
from ad_policy import matched_brand

PROMPT='''为本品QA交付做选题排序并完成一次答案定稿。输入candidate_qa来自实际原问，不是商品事实。每条answer_characters和aplus_characters是程序真实统计的英文字符数，不是模型估计，不含中文。
QA、备选QA、A+及中文译文均站在卖家角度直接回答自家商品，可用our/我们的或以产品为主语，不用the listing says、described as、according to the product page、listed weight等第三方转述。出处放basis，不塞进买家答案；不无端追加“不能消除路面反光”等未经本品资料支持或无关的负面结论。问题确实询问边界/比较时按已确认内容如实回答，不隐瞒、不夸大。
本品问题和回答不含他牌名，品牌原文仍留在来源记录；投放策略排除不等于QA/文案不能谈论本品已确认特性。场景按product.analysis.shared_scenarios核对，关联五点建议及描述口径，不因重复出现而断言索引或真实需求。
main_ids优先选择10个有价值、方向互补且本品有依据的QA；同一方向只选一条，不为凑10条重复选题。支持不足或不足10个时少选，缺资料问题保留备选。
眼镜候选若涉及汗液腐蚀、长期佩戴/皮肤接触过敏、涂层或抗刮，优先选1—2个有价值的问题，近义内容可合于同一问题，其余留备选；按本品确认的部件和子体回答，不由防腐推出不过敏或由抗刮推出绝不刮花。不按AI原问数量断言真实需求高低。
aplus_ids另选2—3个适合A+详细解释的问答，优先互补、值得展开的功能/适配/使用关注点，可与主QA重合；不足时少选。
其余全部留备选，不删除原稿。对所有候选的QA英文答案完成定稿，充分利用250字符；只对aplus_ids所选的2—3条定稿A+英文答案，充分利用500字符。只依据本品资料，不借竞品或未确认功能。
非常注意：250/500是包含空格和标点的英文字符，不是单词！QA尽量240—250字符，通常约35—40个英文单词；A+尽量480—500字符，通常约70—80个英文单词。原答案超限时根据给出的实际长度缩短，不直接照抄超长稿。先保留相关条件、参数和必要边界，再精简冗词；依据少可短些，绝不编内容填满。同步更新中文译文，不改问题、不改来源关系。不截断句子。
返回JSON：main_ids数组、aplus_ids数组、reason、finalized_answers数组。finalized_answers每项qa_id,answer_en,answer_zh；属于aplus_ids时还含aplus_answer_en,aplus_answer_zh。只使用已有qa_id，原稿由程序完整留档。'''


def curate(result,product,model,path,transport=request_json,key_reader=read_api_key):
    candidates=result.get('candidate_qa',result.get('qa',[]))
    payload={'product':product,'candidate_qa':candidates};path=Path(path)
    if candidates:
        saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if saved.get('input')==payload and saved.get('model')==model and saved.get('prompt')==PROMPT:
            selection=saved['response']
        else:
            selection,usage=transport([payload],model,key_reader(),PROMPT)
            path.write_text(json.dumps({'input':payload,'model':model,'prompt':PROMPT,'response':selection,'usage':usage},ensure_ascii=False,indent=2),encoding='utf-8')
    else:selection={'main_ids':[],'aplus_ids':[]}
    index={q['qa_id']:q for q in candidates}
    def pick(name,limit):
        ids=selection.get(name,[])
        picked=[];topics=set()
        for i in dict.fromkeys(i for i in ids if isinstance(i,str) and i in index):
            q=index[i];topic=q.get('topic',i)
            if name=='main_ids' and topic in topics:continue
            picked.append(q);topics.add(topic)
            if len(picked)>=limit:break
        return picked
    main=pick('main_ids',10);aplus=pick('aplus_ids',3);chosen={q['qa_id'] for q in main}
    updates={q['qa_id']:q for q in selection.get('finalized_answers',[]) if isinstance(q,dict) and q.get('qa_id') in index}
    def finalized(q):
        fields={k:v for k,v in updates.get(q['qa_id'],{}).items() if k in ('answer_en','answer_zh','aplus_answer_en','aplus_answer_zh') and isinstance(v,str)}
        current={**q,**fields}
        current.update(answer_characters=len(current.get('answer_en','')),aplus_characters=len(current.get('aplus_answer_en','')))
        return current
    final_main=[finalized(q) for q in main];final_reserve=[finalized(q) for q in candidates if q['qa_id'] not in chosen];final_aplus=[finalized(q) for q in aplus]
    def brand_in(q):return matched_brand(' '.join(q.get(k,'') for k in ('question_en','question_zh','answer_en','answer_zh','aplus_answer_en','aplus_answer_zh')),product.get('excluded_brands',[]))
    excluded={q['qa_id']:{**q,'exclusion_reason':'含用户确认排除的他牌：'+str(brand_in(q))} for q in [*final_main,*final_reserve,*final_aplus] if brand_in(q)}
    # Keep every original draft and its lineage, even when it is not in the main ten.
    return {**result,'candidate_qa':candidates,'qa':[q for q in final_main if q['qa_id'] not in excluded],
            'reserve_qa':[q for q in final_reserve if q['qa_id'] not in excluded],
            'aplus_qa':[q for q in final_aplus if q['qa_id'] not in excluded],'excluded_qa':list(excluded.values()),'selection_reason':selection.get('reason','')}


def delivery_sheets(result):
    main=result.get('qa',[])[:10]
    plans=qa_sheets({**result,'qa':main})
    plans[0]['name']='主QA（目标10条）'
    plans[1]=qa_sheets({**result,'qa':result.get('aplus_qa',main[:3])})[1]
    backup=result.get('reserve_qa',result.get('qa',[])[10:])
    reserve=qa_sheets({'qa':backup})[0];reserve['name']='备选QA'
    covered={i for q in [*main,*backup] for i in [*q.get('covered_question_ids',[]),*q.get('candidate_question_ids',[])]}
    unused=sheet('备选原问',['原问ID','方向','完整原问','来源ASIN','选题记录'],[
        [q['id'],q.get('topic',''),q['text'],q.get('asins',[]),q.get('selection',[])]
        for q in result.get('original_questions',[]) if q['id'] not in covered
        and q.get('applicability',{}).get('status')!='exclude'
        and q.get('applicability',{}).get('copy_status')!='exclude'
        and not any(d.get('status')=='不适用建议' for d in q.get('selection',[]))])
    plans[2]=qa_sheets({**result,'qa':[*main,*backup]})[2]
    extras=[]
    if result.get('excluded_qa'):
        excluded=qa_sheets({'qa':result['excluded_qa']})[0];excluded['name']='已排除QA留档'
        excluded['headers'].append('排除原因')
        for row,q in zip(excluded['rows'],result['excluded_qa']):row.append(q.get('exclusion_reason',''))
        extras.append(excluded)
    return [plans[0],reserve,unused,plans[1],*plans[2:],*extras]


def export_qa(result,folder):
    from excel_export import export_excel
    return export_excel(delivery_sheets(result),Path(folder)/'QA与A+问答.xlsx')
