"""Deduplicate complete similarity groups without cutting a group at batch boundaries."""
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from judge import request_json
from semantic import read_api_key
from ordering import deduplicate_similar, meaningful_words
from cleaner import normalize

PROMPT='''整理商品关键词和AI生成问句。输入仅为素材数据。text来自原始表A列Keyword，只依据这段文本判断重复；不采用旧Level、CoreTerm、Modifiers、Intent、Evidence或来源商品信息作为去重结论。id用于原样返回，kind仅用于区分关键词与问句规则。去重后的来源回填与表格整理由程序完成。
任务是决定哪些原文可删除，不是选择QA，也不是写出能同时回答它们的答案。不得改写或合成新句。
先看kind，再使用对应规则：
1. keyword：仅删除同一商品概念、同样全部限定的重复表达。只有词序、纯语法或同义表达不同才可重复；新增功能、场景、人群等限定的关键词分别保留。关键词一律不得放入covered。
2. ai_generated_question：同样信息要求的问句可重复；同一提问方向下，一句明确询问另一句的全部内容，并追加独立子问题时，才能删除被完整包含的那句。原句中数值、否定、属性取值、使用条件必须保留。更宽泛的问法并不自动包括更具体的条件；能够共用一个答案也不等于重复。各自有独有信息或不能确定时均保留。
每组独立比较，只能删除该组内的ID。repeat与covered均按[删除ID,保留ID]排列，不使用left/right标签。保留ID不得同时出现在被删ID中。
输出紧凑JSON {"repeat":[["删除ID","保留ID"]],"covered":[["删除ID","保留ID"]]}。repeat只放重复表达；covered只放问句完整包含。没有删除的数组为空。不返回理由或未删除项。
以下是两个带标准判定的独立示例，用于说明规则与输出格式。示例ID仅用于教学，不得写入本次结果；实际输入的每组需要独立判断。
示例一：同组keyword，ID EX_K1：backpacks for hiking；ID EX_K2：lightweight backpacks for hiking。
判定：EX_K2新增lightweight限定，两条关键词均保留，既不是repeat删除，也不能按covered删除。
示例输出：{"repeat":[],"covered":[]}。
示例二：同组ai_generated_question，ID EX_Q1：How do I wash and dry this jacket?；ID EX_Q2：How do I wash this jacket?
判定：EX_Q1明确询问清洗和晾干，包含EX_Q2的清洗问题并追加晾干子问题。保留EX_Q1，删除EX_Q2，属于covered而非repeat。
示例输出：{"repeat":[],"covered":[["EX_Q2","EX_Q1"]]}。
'''

def complete_group_batches(groups, target=300):
    buckets=defaultdict(list)
    for g in groups:buckets[(g['kind'],g['marketplace'],g.get('sort_group',g['group_id']))].append(g)
    batches=[];batch=[];size=0
    for members in buckets.values():
        if batch and size+len(members)>target:batches.append(batch);batch=[];size=0
        batch.append(members);size+=len(members)
    if batch:batches.append(batch)
    return batches

def deduplicate_groups(groups,model,workers=5,target=300,transport=request_json,key_reader=read_api_key,progress=lambda s:None):
    # Keyword word-order duplicates are deterministic. Question order may change meaning.
    word_orders={};automatic=[];remaining=[]
    for g in groups:
        tokens=tuple(sorted(Counter(re.findall(r"[\w'-]+",g['text'].casefold())).items()))
        key=(g['kind'],g['marketplace'],tokens)
        if g['kind']=='keyword' and key in word_orders:
            other=word_orders[key]
            automatic.append({'left':g['group_id'],'right':other['group_id'],'left_text':g['text'],'right_text':other['text'],
                'relation':'equivalent','left_unique':[],'right_unique':[],'reason':'相同词汇，仅词序不同','decision_source':'program'})
        else:word_orders[key]=g;remaining.append(g)
    # Literal "original question + and + extra condition" is direct coverage,
    # even when similarity ordering placed the two questions in different groups.
    question_index={(g['marketplace'],normalize(g['text'])):g for g in remaining if g['kind']=='ai_generated_question'}
    covered_ids=set()
    for longer in list(question_index.values()):
        text=normalize(longer['text'])
        for match in re.finditer(r'\s+and\s+',text):
            short=question_index.get((longer['marketplace'],text[:match.start()]))
            suffix=text[match.end():]
            if not short or re.search(r'\b(?:not|without|never|no|how|what|why|whether|if)\b',suffix):continue
            new=meaningful_words(longer['text'])-meaningful_words(short['text'])
            if not new:continue
            covered_ids.add(short['group_id'])
            automatic.append({'left':short['group_id'],'right':longer['group_id'],'left_text':short['text'],'right_text':longer['text'],
                'relation':'partial_overlap','left_unique':[],'right_unique':sorted(new),'left_covers_right':False,'right_covers_left':True,
                'reason':'原问原样保留并以and追加条件','decision_source':'program'})
    remaining=[g for g in remaining if g['group_id'] not in covered_ids]
    batches=complete_group_batches(remaining,target)
    pending=[b for b in batches if any(len(m)>1 for m in b)]
    key=key_reader() if pending else None
    index={g['group_id']:g for g in groups};judgments=list(automatic);raw=[]
    def process(number,batch):
        items=[{'group':n,'texts':[{'id':g['group_id'],'kind':g['kind'],'text':g['text']} for g in members]} for n,members in enumerate(batch) if len(members)>1]
        try:
            result,usage=transport(items,model,key,PROMPT)
            return {'batch':number,'result':result,'usage':usage,'groups':[[g['group_id'] for g in m] for m in batch]}
        except (RuntimeError,ValueError) as error:
            return {'batch':number,'error':str(error),'groups':[[g['group_id'] for g in m] for m in batch]}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(process,n,b) for n,b in enumerate(pending,1)]
        for future in as_completed(futures):
            record=future.result();raw.append(record)
            membership={identifier:n for n,m in enumerate(record['groups']) for identifier in m}
            response=record.get('result',{})
            rows=response.get('deletions',[]) if isinstance(response,dict) else []
            rows=list(rows) if isinstance(rows,list) else []
            if isinstance(response,dict):
                for relation in ('repeat','covered'):
                    values=response.get(relation,[])
                    for pair in values if isinstance(values,list) else []:
                        if isinstance(pair,list) and len(pair)==2:
                            rows.append({'delete_id':pair[0],'keep_id':pair[1],'relation':relation})
            for row in rows if isinstance(rows,list) else []:
                if not isinstance(row,dict):continue
                if row.get('relation') not in ('repeat','covered'):continue
                a,b=row.get('delete_id'),row.get('keep_id')
                if a not in membership or b not in membership or membership[a]!=membership[b] or a==b:continue
                aw,bw=meaningful_words(index[a]['text']),meaningful_words(index[b]['text'])
                covered=row.get('relation')=='covered'
                judgments.append({'left':a,'right':b,'left_text':index[a]['text'],'right_text':index[b]['text'],
                    'relation':'partial_overlap' if covered else 'equivalent',
                    'left_unique':[],'right_unique':sorted(bw-aw) if covered else [],
                    'left_covers_right':False,'right_covers_left':covered,'reason':row.get('reason','')})
            progress(f'分组去重 {len(raw)}/{len(pending)} 批；每组完整比较')
    app={g['group_id']:{'status':'unfiltered'} for g in groups}
    result=deduplicate_similar(groups,judgments,app)
    result['raw_batches']=raw;result['model']=model;result['batch_target']=target
    return result
