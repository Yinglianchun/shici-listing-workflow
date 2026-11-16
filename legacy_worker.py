"""Run visual-workbench stages in a separate process; credentials come only from its environment."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter
from cleaner import load,deduplicate,write_csv
from grading import analyse,prepare_items,compute_level
from semantic import embed_texts,semantic_candidates
from judge import judge_pairs
from applicability import assess
from materials import build,export
from finalize import final_comparison,compose_reviewed
from excel_export import export_excel
from handoff import write_handoff

STAGES=['导入与基础去重','属性分级','独立QA选题','语义关系整理','本品适用性筛选','归并与短语清洗','合并前本品自查','前缀合并与广告词','描述组合与导出']


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def sheet(name,headers,rows):return {'name':name,'headers':headers,'rows':rows}


def run(folder,until=9,compose_only=False):
    folder=Path(folder);cfg=read(folder/'job.json');product=cfg['product'];model=cfg['llm_model']
    status=read(folder/'status.json') if (folder/'status.json').exists() else {'steps':[{'name':s,'state':'pending'} for s in STAGES]}
    status['state']='running';status['error']='';save(folder/'status.json',status)
    cache=Path(__file__).parent/'output'
    if not (folder/'00_本品资料.xlsx').exists():
        export_excel([sheet('本品完整资料',['ASIN','标题','完整详情','待确认事项','资料来源'],[[product['asin'],product.get('title',''),product.get('raw_details',product.get('facts',{})),product.get('pending_questions',[]),'用户提供']])],folder/'00_本品资料.xlsx')
    def begin(index):
        status['current']=index;status['steps'][index-1]['state']='running';save(folder/'status.json',status)
        print(f'阶段 {index}/9：{STAGES[index-1]}',flush=True)
    def done(index,plans):
        path=folder/f'{index:02d}_{STAGES[index-1]}.xlsx'
        export_excel(plans,path)
        status['steps'][index-1].update(state='done',file=path.name)
        save(folder/'status.json',status)
        write_handoff(folder)
    def ready(index):return (folder/f'stage{index}.json').exists() and status['steps'][index-1]['state']=='done' and (folder/status['steps'][index-1].get('file','')).is_file() and not compose_only
    try:
        if not compose_only:
            if not ready(1):
                begin(1);sources=load([Path(p) for p in cfg['inputs']]);groups=deduplicate(sources)
                save(folder/'stage1.json',{'sources':sources,'groups':groups})
                done(1,[sheet('原始来源',['来源ID','文件','CSV位置','ASIN','类型','原文'],[[s['source_id'],Path(s['file']).name,s['csv_record'],s['raw']['ASIN'],s['raw']['Type'],s['raw']['Keyword']] for s in sources]),
                    sheet('基础去重',['文本组','类型','原文','来源ID','ASIN'],[[g['group_id'],g['kind'],g['text'],', '.join(g['sources']),', '.join(g['asins'])] for g in groups])])
            stage1=read(folder/'stage1.json');sources=stage1['sources'];groups=stage1['groups']
            if until==1:return
            if not ready(2):
                begin(2);assessments,stats=analyse(prepare_items(groups,sources),cache/'assessment-cache.sqlite3',model=model,progress=lambda s:print(s,flush=True))
                graded=[]
                for g in groups:
                    a=assessments[g['group_id']]
                    a=compute_level(a,g['kind']) if 'error' not in a else {**a,'level':None,'proposed_level':None,'grading_status':'failed','grading_reasons':[a['error']]}
                    graded.append({**g,'assessment':a})
                save(folder/'stage2.json',graded)
                plans=[]
                for kind,label in [('keyword','关键词'),('ai_generated_question','问句')]:
                    levels=sorted({g['assessment'].get('level') for g in graded if g['kind']==kind},key=lambda v:v if isinstance(v,int) else 99)
                    for level in levels:
                        rows=[g for g in graded if g['kind']==kind and g['assessment'].get('level')==level]
                        plans.append(sheet(label+(f'{level}级' if level is not None else '待复核'),['原文ID','原文','等级','核心词','属性','方向','复核原因'],[[g['group_id'],g['text'],level,g['assessment'].get('core_term',''),g['assessment'].get('attributes',[]),g['assessment'].get('topic',''),g['assessment'].get('grading_reasons',[])] for g in rows]))
                done(2,plans or [sheet('无分级结果',['说明'],[['原始记录仍保留']])])
            graded=read(folder/'stage2.json');a={g['group_id']:g['assessment'] for g in graded}
            if until==2:return
            if not ready(3):
                begin(3);qa_input=folder/'qa_input';qa_input.mkdir(exist_ok=True)
                save(qa_input/'groups.json',groups);save(qa_input/'sources.json',sources);save(qa_input/'graded_groups.json',graded)
                save(folder/'product.json',product)
                subprocess.run([sys.executable,str(Path(__file__).parent/'qa.py'),'--input',str(qa_input),'--assessments',str(qa_input),'--product',str(folder/'product.json'),'--model',model,'--out',str(folder/'qa')],check=True)
                qa=read(folder/'qa/qa_selection.json');save(folder/'stage3.json',qa)
                done(3,[sheet('QA选题与回答',['编号','方向','英文问题','中文问题','QA英文回答','中文译文','A+英文回答','A+中文译文','依据','待补资料'],[[q['qa_id'],q['topic'],q.get('question_en',''),q.get('question_zh',''),q.get('answer_en',''),q.get('answer_zh',''),q.get('aplus_answer_en',''),q.get('aplus_answer_zh',''),q.get('basis',''),q.get('pending_questions',[])] for q in qa['qa']])])
            qa=read(folder/'stage3.json')
            if until==3:return
            if not ready(4):
                begin(4);vectors,_=embed_texts([g['text'] for g in groups],cache/'embedding-cache.sqlite3',model=cfg['embedding_model'],progress=lambda s:print(s,flush=True))
                candidates,_=semantic_candidates(groups,vectors)
                judgments,stats=judge_pairs(candidates,groups,cache/'judgment-cache.sqlite3',model=model,progress=lambda s:print(s,flush=True))
                save(folder/'stage4.json',judgments)
                done(4,[sheet('语义关系',['左原文','右原文','关系建议','左独有','右独有','可共用答案','理由'],[[j['left_text'],j['right_text'],j.get('relation'),j.get('left_unique',[]),j.get('right_unique',[]),j.get('can_share_answer'),j.get('reason',j.get('error',''))] for j in judgments])])
            judgments=read(folder/'stage4.json')
            if until==4:return
            if not ready(5):
                begin(5);app,stats=assess(groups,product,cache/'applicability-cache.sqlite3',model=model)
                save(folder/'stage5.json',app)
                done(5,[sheet('本品适用性',['原文ID','原文','建议','原因','资料依据','待补资料'],[[g['group_id'],g['text'],app[g['group_id']].get('status'),app[g['group_id']].get('reason'),app[g['group_id']].get('basis'),app[g['group_id']].get('missing_information',[])] for g in groups])])
            app=read(folder/'stage5.json')
            if until==5:return
            if not ready(6):
                begin(6);materials=build(groups,a,app,judgments,qa,product['asin'],cfg['max_characters'],compose=False)
                save(folder/'stage6.json',materials)
                done(6,[sheet(name,['素材ID','等级','完整原文','清洗短语','合并前全部原文','来源ID'],[[r['material_id'],r['level'],r['text'],r['phrase'],r['originals'],r['sources']] for r in materials['materials'] if r['kind']==kind]) for kind,name in [('keyword','关键词素材'),('ai_generated_question','问句与清洗短语')]])
            if until==6:return
            if not ready(7):
                begin(7);materials=read(folder/'stage6.json')
                reviews,stats=final_comparison(materials['materials'],product,cache/'final-check-cache.sqlite3',model)
                save(folder/'stage7.json',reviews)
                done(7,[sheet('合并前再次比对',['素材ID','等级','完整原文','清洗后','自查建议','原因','本品依据','待补资料'],[[r['material']['material_id'],r['material']['level'],r['material']['text'],r['material']['phrase'],r['review'].get('status'),r['review'].get('reason'),r['review'].get('basis'),r['review'].get('missing_information',[])] for r in reviews])])
            if until==7:return
        reviews=read(folder/'stage7.json')
        if (folder/'review_decisions.json').exists():
            changes=read(folder/'review_decisions.json')
            for row in reviews:
                row['model_review']=dict(row['review'])
                if row['material']['material_id'] in changes:row['review']={**row['review'],**changes[row['material']['material_id']]}
            done(7,[sheet('合并前再次比对',['素材ID','等级','完整原文','清洗后','自查建议','原因','本品依据','待补资料','原模型建议','人工修改'],[[r['material']['material_id'],r['material']['level'],r['material']['text'],r['material']['phrase'],r['review'].get('status'),r['review'].get('reason'),r['review'].get('basis'),r['review'].get('missing_information',[]),r['model_review'].get('status'),'是' if r['material']['material_id'] in changes else ''] for r in reviews])])
        begin(8);final=compose_reviewed(reviews,cfg['max_characters']);save(folder/'stage8.json',final)
        done(8,[sheet('完整广告关键词',['关键词','等级','来源ID'],[[r['keyword'],r['level'],r['sources']] for r in final['advertising_keywords']]),
            sheet('共同前缀整理',['整理文本','共同前缀','不同后缀','完整原句'],[[r['text'],r['prefix'],r['suffixes'],[m['text'] for m in r['members']]] for r in final['prefix_groups']])])
        write_csv(folder/'广告关键词.csv',['关键词'],[[r['keyword']] for r in final['advertising_keywords']])
        if until==8:return
        begin(9);save(folder/'stage9.json',final)
        (folder/'商品描述素材草稿.txt').write_text(final['description'],encoding='utf-8',newline='\n')
        done(9,[sheet('描述草稿',['描述素材','实际字符数','字符上限'],[[final['description'],len(final['description']),cfg['max_characters']]]),
            sheet('采用明细',['文本','格式','素材ID'],[[r['text'],r['format'],r.get('material_ids',[])] for r in final['description_selection']])])
        status['summary']={'keywords':len(final['advertising_keywords']),'characters':len(final['description']),'passed':final['passed_count'],'reviewed':final['reviewed_count']}
    except Exception as error:
        status['state']='failed';status['error']=str(error);raise
    finally:
        if status['state']=='running':status['state']='completed' if until>=9 else 'paused'
        save(folder/'status.json',status)
        write_handoff(folder)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--until',type=int,default=9);p.add_argument('--compose-only',action='store_true')
    args=p.parse_args();run(args.job,args.until,args.compose_only)
