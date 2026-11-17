import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import workbench_worker as worker
from naming import named_file,plan_file
from excel_export import portable_excel
from qa import build_candidates
from test_ordering import group,equivalent

class WorkflowTests(unittest.TestCase):
    def test_full_order_pending_qa_resume_and_manual_recompose(self):
        self.run_workflow('sorted-first')

    def test_dedup_first_order_and_resume(self):
        self.run_workflow('dedup-first')

    def test_new_project_analysis_tables_and_resume(self):
        self.run_workflow('dedup-first',modern=True)

    def test_stop_after_sorting_does_not_call_product_analysis(self):
        self.run_workflow('dedup-first',modern=True,stop_first=True)

    def test_single_workbook_dynamic_topics_and_word_resume(self):
        self.run_workflow('dedup-first',modern=True,single=True)

    def test_four_excel_reports_and_ad_only_exclusion_keep_description_material(self):
        self.run_workflow('dedup-first',modern=True,suite=True)

    def test_copy_only_exclusion_does_not_remove_advertising_or_create_negative(self):
        self.run_workflow('dedup-first',modern=True,suite=True,copy_only=True)

    def test_four_workbook_qa_receives_original_questions_excluded_from_ads(self):
        self.run_workflow('dedup-first',modern=True,suite=True,qa_excluded=True)

    def run_workflow(self,flow,modern=False,stop_first=False,single=False,suite=False,copy_only=False,qa_excluded=False):
        single=single or suite
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);incoming=root/'input';incoming.mkdir();job=root/'job';job.mkdir()
            groups=[group('a','polarized sunglasses'),group('b','sunglasses polarized'),group('c','anti glare polarized sunglasses'),group('d','red sunglasses'),group('e','How do I clean these sunglasses?','ai_generated_question'),group('f','Do these sunglasses offer UV400?','ai_generated_question')]
            groups.extend([group('g','Are sunglasses suitable for fishing?','ai_generated_question'),group('h','Are sunglasses suitable for fishing and golf?','ai_generated_question')])
            if qa_excluded:groups.append(group('i','Can these sunglasses hold prescription lenses?','ai_generated_question'))
            sources=[{'source_id':'S'+g['group_id'],'file':'fixture.csv','csv_record':i+1,'raw':{'ASIN':'OWN','Type':g['kind'],'Keyword':g['text'],'CoreTerm':'sunglasses'}} for i,g in enumerate(groups)]
            worker.save(incoming/'sources.json',sources);worker.save(incoming/'groups.json',groups)
            worker.save(job/'job.json',{'workflow':flow,'export_prefix':'OWN_2026-11-15','import_folder':str(incoming),'product':{'asin':'OWN','title':'Test','facts':{'lens':'polarized, UV400, anti glare'}},'llm_model':'test/model','embedding_model':'test/embedding','max_characters':9000})
            if modern:
                cfg=worker.read(job/'job.json');cfg.update(excel_subdir='表格',analyze_product=True);worker.save(job/'job.json',cfg)
                if single:
                    cfg.update(report_mode='four-workbooks' if suite else 'single-workbook',dynamic_qa_topics=True);worker.save(job/'job.json',cfg)
            worker.save(job/'status.json',{'state':'pending','steps':[{'name':name,'state':'pending'} for name in (worker.STAGES if flow=='dedup-first' else worker.SORTED_STAGES)]})
            calls=[];qa_ids=[]
            def export(plans,path):
                path=named_file(Path(path).parent,Path(path).name);path.parent.mkdir(parents=True,exist_ok=True);worker.save(plan_file(path),plans);portable_excel(plans,path);return path
            def analyse_product(product,model,path):
                if path.exists():return worker.read(path)
                calls.append('product')
                result={'product':product,'analysis':{'selling_points':[{'item':'偏光','basis':'polarized'}]}}
                worker.save(path,result);return result
            def discover_topics(groups,product,model,path):
                if qa_excluded:self.assertIn('i',[g['group_id'] for g in groups])
                if path.exists():return ['清洁保养','紫外线防护','其他']
                calls.append('topics');worker.save(path,{'topics':['清洁保养','紫外线防护','其他']})
                return ['清洁保养','紫外线防护','其他']
            def embed(texts,*args,**kwargs):calls.append('embedding');return [[1.,0.] for t in texts],{}
            def assess(items,*args,**kwargs):
                calls.append('applicability')
                if modern:self.assertIn('analysis',args[0])
                return {g['group_id']:{'status':'exclude' if g['group_id'] in ('d','i') else 'pending' if g['group_id']=='e' else 'eligible','reason':'fixture','basis':'fixture',**({'ad_status':'eligible' if copy_only else 'exclude','ad_reason':'campaign choice','copy_status':'eligible'} if suite and g['group_id']=='c' else {})} for g in items},{}
            def judge(pairs,groups,*args,**kwargs):
                calls.append('dedup');index={g['group_id']:g for g in groups}
                return [equivalent(index[p['left']],index[p['right']]) for p in pairs],{}
            def grouped(groups,*args,**kwargs):
                calls.append('dedup')
                from ordering import deduplicate_similar
                judgments=[equivalent(a,b) for a in groups for b in groups if a is not b]
                judgments.append({'left':'g','right':'h','relation':'partial_overlap','left_unique':[],'right_unique':['golf'],'left_covers_right':False,'right_covers_left':True})
                return deduplicate_similar(groups,judgments,{g['group_id']:{'status':'unfiltered'} for g in groups})
            def analyse(items,*args,**kwargs):
                calls.append('grading')
                self.assertNotIn('d',[i['id'] for i in items]);self.assertNotIn('b',[i['id'] for i in items])
                return {i['id']:{'core_term':'sunglasses','attributes':[],'topic':'清洁保养' if single else '包装保养与售后'} for i in items},{}
            def qa_process(args,**kwargs):
                calls.append('qa');qin=Path(args[args.index('--input')+1]);out=Path(args[args.index('--out')+1]);out.mkdir()
                gs=worker.read(qin/'groups.json');graded=worker.read(qin/'graded_groups.json');app=worker.read(qin/'applicability.json')
                topic_names=worker.read(qin/'topics.json') if (qin/'topics.json').exists() else None
                if single:self.assertEqual(topic_names,['清洁保养','紫外线防护','其他'])
                buckets=build_candidates(gs,{g['group_id']:g['assessment'] for g in graded},sources,app,topic_names)
                original=[q for qs in buckets.values() for q in qs];qa_ids.extend(q['id'] for q in original)
                worker.save(out/'qa_selection.json',{'qa':[],'original_questions':original})
            def final(materials,*args,**kwargs):
                calls.append('final')
                self.assertTrue(all('red sunglasses' not in r['originals'] for r in materials))
                return [{'material':r,'review':{'status':'exclude' if copy_only and 'c' in r['member_ids'] else 'eligible','reason':'copy only fixture','ad_status':'eligible'}} for r in materials],{}
            from qa_delivery import delivery_sheets
            with patch.multiple(worker,export_excel=export,export_qa=lambda result,folder:export(delivery_sheets(result),Path(folder)/'QA与A+问答.xlsx'),embed_texts=embed,assess=assess,judge_pairs=judge,deduplicate_groups=grouped,analyse=analyse,analyse_product=analyse_product,discover_topics=discover_topics,final_comparison=final),patch.object(worker.subprocess,'run',qa_process),patch('master_workbook.export_excel',export),patch('product_workbook.export_excel',export):
                if stop_first:
                    worker.run(job,2)
                    self.assertEqual(calls,['embedding'])
                    self.assertFalse((job/'product_analysis.json').exists())
                worker.run(job,9)
                expected=['embedding','product','dedup','applicability','grading','qa','final'] if stop_first else (['product'] if modern else [])+(['embedding','dedup','applicability','grading','qa','final'] if flow=='dedup-first' else ['embedding','applicability','dedup','grading','qa','final'])
                if single:expected.insert(expected.index('grading'),'topics')
                self.assertEqual(calls,expected)
                self.assertCountEqual(qa_ids,['e','f','g','h']+(['i'] if qa_excluded else []))
                if flow=='dedup-first':
                    graded={g['group_id']:g['assessment'] for g in worker.read(job/'stage5.json')}
                    self.assertIsNone(graded['g']['level'])
                    self.assertEqual(graded['h']['level'],0)
                    self.assertEqual(worker.read(job/'stage4.json')['g']['status'],'pending')
                self.assertEqual(worker.read(job/('stage3.json' if flow=='dedup-first' else 'stage4.json'))['representatives']['b'],'a')
                self.assertIn('c',worker.read(job/('stage3.json' if flow=='dedup-first' else 'stage4.json'))['kept_ids'])
                tables=list(job.rglob('*.xlsx'));tables=[p for p in tables if '使用的Skill' not in p.parts]
                self.assertEqual(len(tables),4 if suite else 2 if single else 12 if modern else 11)
                self.assertTrue(all(p.name.startswith('OWN_2026-11-15_') for p in tables))
                if modern:
                    self.assertFalse(list(job.glob('*.xlsx')))
                    self.assertFalse(list((job/'表格').glob('*.json')))
                    self.assertTrue(all(s['file'].startswith('表格/') for s in worker.read(job/'status.json')['steps']))
                    self.assertIn('analysis',worker.read(job/'product.json'))
                self.assertEqual(worker.read(job/'status.json')['state'],'completed')
                if single:
                    self.assertEqual(len(list(job.glob('*.docx'))),0 if suite else 1)
                    self.assertEqual(len({s['file'] for s in worker.read(job/'status.json')['steps']}),3 if suite else 2)
                if suite:
                    reviews=worker.read(job/'stage7.json')
                    c=next(r for r in reviews if 'c' in r['material']['member_ids'])
                    self.assertEqual(c['review']['status'],'exclude' if copy_only else 'eligible')
                    advertised=[r['keyword'] for r in worker.read(job/'stage8.json')['advertising_keywords']]
                    self.assertEqual('anti glare polarized sunglasses' in advertised,copy_only)
                    negatives=worker.read(job/'stage8.json')['negative_keyword_candidates']
                    self.assertFalse(any(r['text']=='anti glare polarized sunglasses' and r['reason'].startswith('明确不符') for r in negatives))
                worker.run(job,6);self.assertEqual(len(calls),len(expected))
                reviews=worker.read(job/'stage7.json');mid=next(r['material']['material_id'] for r in reviews if r['material']['kind']=='keyword')
                worker.save(job/'review_decisions.json',{mid:{'status':'exclude','reason':'manual'}})
                worker.run(job,9,compose_only=True);self.assertEqual(len(calls),len(expected))
                self.assertNotIn(mid,[r['material_id'] for r in worker.read(job/'stage8.json')['advertising_keywords']])

if __name__=='__main__':unittest.main()
