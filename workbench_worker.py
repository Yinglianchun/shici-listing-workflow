"""Staged listing workflow: order, screen, deduplicate, classify, QA, clean/review, export."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from cleaner import load,deduplicate,write_csv
from grading import analyse,prepare_items,compute_level
from semantic import embed_texts
from judge import judge_pairs
from applicability import assess
from materials import build
from finalize import final_comparison,compose_reviewed,negative_candidates
from excel_export import export_excel
from handoff import write_handoff
from ordering import rank_groups,active_groups,duplicate_candidates,deduplicate_similar,restore_lineage,meaningful_words
from keyword_layout import keyword_sheets
from naming import named_file
from group_dedup import deduplicate_groups
from product_analysis import analyse_product,analysis_sheets
from master_workbook import update_master
from qa_topics import discover_topics
from word_export import export_description
from qa_delivery import export_qa
from output_plans import screened_sheets,question_grade_sheets,cleaned_question_sheets,prefix_sheets,description_sheets,approved_ids,qa_sheets

SORTED_STAGES=['导入与基础去重','相似素材排序分组','本品适用性筛选','高重合素材去重','方向分类与属性分级','独立QA选题与回答','短语清洗与本品复核','前缀整理与广告词','描述组合与导出']
STAGES=[*SORTED_STAGES[:2],SORTED_STAGES[3],SORTED_STAGES[2],*SORTED_STAGES[4:]]

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def sheet(name,headers,rows):return {'name':name,'headers':headers,'rows':rows}

def run(folder,until=9,compose_only=False):
    folder=Path(folder);cfg=read(folder/'job.json')
    if cfg.get('workflow') not in ('sorted-first','dedup-first'):
        from legacy_worker import run as old_run
        return old_run(folder,until,compose_only)
    new_order=cfg.get('workflow')=='dedup-first'
    single=cfg.get('report_mode')=='single-workbook'
    stages=STAGES if new_order else SORTED_STAGES
    product=cfg['product'];model=cfg['llm_model'];cache=Path(cfg.get('cache_dir',Path(__file__).parent/'output'))
    status=read(folder/'status.json');status.update(state='running',error='');status.setdefault('started_at',time.time());save(folder/'status.json',status)
    def begin(index):
        status['current']=index;status['steps'][index-1]['state']='running';save(folder/'status.json',status)
        print(f'阶段 {index}/9：{stages[index-1]}',flush=True)
    def done(index,plans):
        path=update_master(folder,index,plans) if single else export_excel(plans,folder/f'{index:02d}_{stages[index-1]}.xlsx')
        if single and index==6:path=export_qa(read(folder/'stage6.json'),folder)
        status['steps'][index-1].update(state='done',file=path.relative_to(folder).as_posix());save(folder/'status.json',status);write_handoff(folder)
    def question_details(plans):
        if single:save(folder/'stage5_questions.plan.json',plans)
        else:export_excel(plans,folder/'05_问句与分级明细.xlsx')
    def ready(index):return (folder/f'stage{index}.json').is_file() and status['steps'][index-1]['state']=='done' and (folder/status['steps'][index-1].get('file','')).is_file()
    try:
        save(folder/'product.json',product)
        if cfg.get('analyze_product') and until>=3 and not compose_only:
            print('阶段 00：本品卖点与资料冲突分析',flush=True)
            status['product_analysis_state']='running';save(folder/'status.json',status)
            analysed=analyse_product(product,model,folder/'product_analysis.json')
            analysis_path=update_master(folder,0) if single else export_excel(analysis_sheets(analysed['analysis']),folder/'00_本品分析.xlsx')
            product={**product,'analysis':analysed['analysis']}
            save(folder/'product.json',product)
            status.update(product_analysis_state='done',product_analysis_file=analysis_path.relative_to(folder).as_posix())
            save(folder/'status.json',status)
        elif (folder/'product_analysis.json').exists():
            product={**product,'analysis':read(folder/'product_analysis.json')['analysis']}
        if not single and not named_file(folder,'00_本品资料.xlsx').exists():
            export_excel([sheet('本品完整资料',['ASIN','标题','完整详情','待确认事项','资料来源'],[[product['asin'],product.get('title',''),product.get('raw_details',product.get('facts',{})),product.get('pending_questions',[]),product.get('source_type','用户提供')]])],folder/'00_本品资料.xlsx')
        if not compose_only:
            if not ready(1):
                begin(1)
                if cfg.get('import_folder'):
                    imported=Path(cfg['import_folder']);sources=read(imported/'sources.json');groups=read(imported/'groups.json')
                else:sources=load([Path(p) for p in cfg['inputs']]);groups=deduplicate(sources)
                save(folder/'stage1.json',{'sources':sources,'groups':groups})
                done(1,[sheet('原始来源',['来源ID','文件','CSV位置','ASIN','类型','原文'],[[s['source_id'],Path(s['file']).name,s['csv_record'],s['raw']['ASIN'],s['raw']['Type'],s['raw']['Keyword']] for s in sources]),sheet('基础去重',['原文ID','类型','完整原文','来源ID','ASIN'],[[g['group_id'],g['kind'],g['text'],g['sources'],g['asins']] for g in groups])])
            imported=read(folder/'stage1.json');sources=imported['sources'];groups=imported['groups']
            if until==1:return
            if not ready(2):
                begin(2);vectors,_=embed_texts([g['text'] for g in groups],cache/'embedding-cache.sqlite3',model=cfg['embedding_model'],progress=lambda s:print(s,flush=True))
                ranked=rank_groups(groups,vectors);save(folder/'stage2.json',ranked)
                done(2,[sheet('排序分组',['排序','相似组','直接比较代表','原文ID','类型','完整原文','来源ID'],[[g['sort_order'],g['sort_group'],g['sort_anchor'],g['group_id'],g['kind'],g['text'],g['sources']] for g in ranked['groups']]),sheet('相似候选',['左ID','右ID','左原文','右原文','语义相似度','文字重合度','左新词','右新词'],[[p['left'],p['right'],p['left_text'],p['right_text'],p['score'] if p['score_type']=='embedding_cosine' else '',p['token_overlap'],p['left_only_tokens'],p['right_only_tokens']] for p in ranked['candidates']])])
            ranked=read(folder/'stage2.json');groups=ranked['groups']
            if until==2:return
            if new_order:
                if not ready(3):
                    begin(3)
                    if cfg.get('reuse_judgments'):
                        dedup=deduplicate_similar(groups,read(cfg['reuse_judgments']),{g['group_id']:{'status':'unfiltered'} for g in groups})
                    else:dedup=deduplicate_groups(groups,cfg.get('screen_model',model),progress=lambda s:print(s,flush=True))
                    save(folder/'stage3.json',dedup)
                    done(3,[sheet('去重与保留',['原文ID','完整原文','代表ID','决定','原因'],[[r['id'],r['text'],r['representative_id'],r['decision'],r['reason']] for r in dedup['decisions']]),sheet('关系原始建议',['左ID','右ID','左原文','右原文','关系','左独有信息','右独有信息','原因'],[[j['left'],j['right'],j.get('left_text',''),j.get('right_text',''),j.get('relation'),j.get('left_unique',[]),j.get('right_unique',[]),j.get('reason','')] for j in dedup['judgments']])])
                dedup=read(folder/'stage3.json');roots=dedup['representatives']
                if until==3:return
                if not ready(4):
                    begin(4);to_screen=[g for g in groups if g['group_id'] in dedup['kept_ids']]
                    app=read(cfg['reuse_applicability']) if cfg.get('reuse_applicability') else assess(to_screen,product,cache/'applicability-cache.sqlite3',model=cfg.get('screen_model',model))[0]
                    by_id={g['group_id']:g for g in groups}
                    for g in groups:
                        identifier=g['group_id'];representative=roots[identifier]
                        if identifier not in app:
                            same=meaningful_words(g['text'])==meaningful_words(by_id[representative]['text'])
                            app[identifier]={**app.get(representative,{})} if same else {'status':'pending','reason':'去重阶段已剔除；完整原问保留给QA，未单独筛选本品适用性'}
                    if cfg.get('decisions'):
                        decisions={(r['kind'],r['text']):r for r in read(cfg['decisions'])}
                        for g in groups:
                            decision=decisions.get((g['kind'],g['text']))
                            if decision:app[g['group_id']]={**app.get(g['group_id'],{}),**decision,'decision_source':'manual'}
                    save(folder/'stage4.json',app)
                    done(4,screened_sheets(to_screen,app))
                app=read(folder/'stage4.json');active=active_groups(groups,app)
            elif not ready(3):
                begin(3)
                app=read(cfg['reuse_applicability']) if cfg.get('reuse_applicability') else assess(groups,product,cache/'applicability-cache.sqlite3',model=model)[0]
                if cfg.get('decisions'):
                    decisions={(r['kind'],r['text']):r for r in read(cfg['decisions'])}
                    for g in groups:
                        decision=decisions.get((g['kind'],g['text']))
                        if decision:app[g['group_id']]={**app.get(g['group_id'],{}),**decision,'decision_source':'manual'}
                save(folder/'stage3.json',app)
                done(3,screened_sheets(groups,app))
            if not new_order:app=read(folder/'stage3.json');active=active_groups(groups,app)
            if until==3:return
            if not new_order and not ready(4):
                begin(4);pairs=duplicate_candidates(ranked['candidates'],active)
                if cfg.get('reuse_judgments'):judgments=read(cfg['reuse_judgments'])
                else:judgments=judge_pairs(pairs,active,cache/'judgment-cache.sqlite3',model=model,progress=lambda s:print(s,flush=True))[0] if pairs else []
                dedup=deduplicate_similar(active,judgments,app);save(folder/'stage4.json',dedup)
                done(4,[sheet('去重与保留',['原文ID','完整原文','代表ID','决定','原因'],[[r['id'],r['text'],r['representative_id'],r['decision'],r['reason']] for r in dedup['decisions']]),sheet('关系原始建议',['左ID','右ID','左原文','右原文','关系','左独有信息','右独有信息','原因'],[[j['left'],j['right'],j['left_text'],j['right_text'],j.get('relation'),j.get('left_unique',[]),j.get('right_unique',[]),j.get('reason','')] for j in judgments])])
            if not new_order:dedup=read(folder/'stage4.json')
            roots=dedup['representatives'];kept=[g for g in active if g['group_id'] in dedup['kept_ids']]
            if until==4:return
            topic_names=cfg.get('topics') or None
            if cfg.get('dynamic_qa_topics') and not topic_names:
                topic_names=discover_topics(active,product,model,folder/'qa_topics.json')
            if topic_names:save(folder/'topics.json',topic_names)
            if not ready(5):
                begin(5);existing={(g['kind'],g['marketplace'],g['text']):g['assessment'] for f in cfg.get('reuse_grades',[]) for g in read(f)}
                assessments={g['group_id']:existing[(g['kind'],g['marketplace'],g['text'])] for g in kept if (g['kind'],g['marketplace'],g['text']) in existing}
                missing=[g for g in kept if g['group_id'] not in assessments]
                if missing:assessments.update(analyse(prepare_items(missing,sources),cache/'assessment-cache.sqlite3',model=model,progress=lambda s:print(s,flush=True),topics=topic_names)[0])
                for g in kept:
                    a=assessments[g['group_id']];a=compute_level(a,g['kind']) if 'error' not in a else {**a,'level':None,'grading_reasons':[a['error']]}
                    if 'level' in app[g['group_id']]:a={**a,'level':app[g['group_id']]['level']}
                    assessments[g['group_id']]=a
                graded=[{**g,'assessment':{**assessments.get(roots[g['group_id']],{'level':None,'attributes':[],'topic':'其他'}),'inherited_from':roots[g['group_id']]}} for g in active]
                if new_order:
                    by_id={g['group_id']:g for g in groups}
                    for g in graded:
                        root=roots[g['group_id']]
                        if meaningful_words(g['text'])!=meaningful_words(by_id[root]['text']):
                            g['assessment']={**g['assessment'],'level':None,'attributes':[],'grading_reasons':['覆盖删除的原问仅供QA参考，不继承较长问题的属性等级']}
                save(folder/'stage5.json',graded)
                question_details(question_grade_sheets(graded,app,roots))
                done(5,keyword_sheets(graded,groups,sources,app,roots,product))
            graded=read(folder/'stage5.json');assessments={g['group_id']:g['assessment'] for g in graded}
            if until==5:return
            if not ready(6):
                begin(6)
                if cfg.get('reuse_qa'):qa=read(cfg['reuse_qa'])
                else:
                    qin=folder/'qa_input';qin.mkdir(exist_ok=True)
                    save(qin/'groups.json',active);save(qin/'sources.json',sources);save(qin/'graded_groups.json',graded);save(qin/'applicability.json',app)
                    if topic_names:save(qin/'topics.json',topic_names)
                    subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).parent/'qa.py'),'--input',str(qin),'--assessments',str(qin),'--product',str(folder/'product.json'),'--model',model,'--out',str(folder/'qa'),*(['--separate-qa'] if single else [])],check=True)
                    qa=read(folder/'qa/qa_selection.json')
                save(folder/'stage6.json',qa)
                done(6,qa_sheets(qa))
            qa=read(folder/'stage6.json')
            if until==6:return
            if not ready(7):
                begin(7);material=build(kept,assessments,app,[],qa,product['asin'],cfg['max_characters'],compose=False)
                restore_lineage(material['materials'],active,roots,qa)
                save(folder/'stage7_materials.json',material)
                reviews,_=final_comparison(material['materials'],product,cache/'final-check-cache.sqlite3',model)
                save(folder/'stage7.json',reviews)
                plans=cleaned_question_sheets(reviews,graded)
                done(7,plans)
        reviews=read(folder/'stage7.json');changes=read(folder/'review_decisions.json') if (folder/'review_decisions.json').exists() else {}
        if single and (folder/'stage6.json').exists():
            qa_path=export_qa(read(folder/'stage6.json'),folder)
            status['steps'][5]['file']=qa_path.relative_to(folder).as_posix()
        for r in reviews:
            mid=r['material']['material_id']
            if mid in changes:r['model_review']=r['review'];r['review']={**r['review'],**changes[mid]}
        # Final product screening also refreshes the earlier graded outputs.
        graded=read(folder/'stage5.json')
        imported=read(folder/'stage1.json');groups=read(folder/'stage2.json')['groups']
        dedup=read(folder/('stage3.json' if new_order else 'stage4.json'))
        app=read(folder/('stage4.json' if new_order else 'stage3.json'))
        ids=approved_ids(reviews)
        final_app={i:{**value,'status':value.get('status') if i in ids else 'exclude'} for i,value in app.items()}
        question_details(question_grade_sheets(graded,final_app,dedup['representatives']))
        done(5,keyword_sheets(graded,groups,imported['sources'],final_app,dedup['representatives'],product))
        done(7,cleaned_question_sheets(reviews,graded))
        if until==7:return
        begin(8);final=compose_reviewed(reviews,cfg['max_characters'])
        negative_app=dict(app)
        for r in reviews:
            for identifier in r['material']['member_ids']:
                negative_app[identifier]={**app.get(identifier,{}),**r['review']}
        final['negative_keyword_candidates']=negative_candidates(groups,negative_app,graded,dedup['representatives'])
        save(folder/'stage8.json',final)
        done(8,prefix_sheets(final))
        if not single:
            write_csv(named_file(folder,'08_广告关键词.csv' if cfg.get('export_prefix') else '广告关键词.csv'),['关键词'],[[r['keyword']] for r in final['advertising_keywords']])
            write_csv(named_file(folder,'08_否定关键词候选.csv'),['完整词句','类型','等级','建议原因','本品依据','来源ID','匹配方式'],
                [[r['text'],r['kind'],r.get('level',''),r['reason'],r.get('basis',''),','.join(r['sources']),'待选择'] for r in final['negative_keyword_candidates']])
        if until==8:return
        begin(9);save(folder/'stage9.json',final)
        if single:export_description(final['description'],named_file(folder,'商品描述素材.docx'),product['asin'],cfg['max_characters'])
        else:named_file(folder,'09_商品描述素材草稿.txt' if cfg.get('export_prefix') else '商品描述素材草稿.txt').write_text(final['description'],encoding='utf-8')
        done(9,description_sheets(final))
        status['summary']={'keywords':sum(r['level']>=2 for r in final['advertising_keywords']) if single else len(final['advertising_keywords']),'characters':len(final['description']),'passed':final['passed_count'],'reviewed':final['reviewed_count']}
    except Exception as error:status.update(state='failed',error=str(error));raise
    finally:
        if status['state']=='running':status['state']='completed' if until>=9 else 'paused'
        status['ended_at']=time.time()
        save(folder/'status.json',status);write_handoff(folder)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--until',type=int,default=9);p.add_argument('--compose-only',action='store_true')
    args=p.parse_args();run(args.job,args.until,args.compose_only)
