import json
import tempfile
import unittest
from pathlib import Path
from handoff import write_handoff,STAGE_NAMES,INPUT_STAGES


class HandoffTests(unittest.TestCase):
    def test_pending_representatives_and_deleted_originals_are_separate(self):
        from handoff import NEW_STAGE_NAMES
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            def save(name,value):(folder/name).write_text(json.dumps(value),encoding='utf-8')
            save('job.json',{'workflow':'dedup-first','excel_subdir':'表格','product':{'asin':'OWN'},'max_characters':9000})
            save('status.json',{'steps':[{'name':name,'state':'done' if i<4 else 'pending',**({'file':f'表格/{i+1:02d}_{name}.xlsx'} if i<4 else {})} for i,name in enumerate(NEW_STAGE_NAMES)]})
            save('stage3.json',{'kept_ids':['a','b'],'groups':[{'group_id':'a','kind':'keyword'},{'group_id':'b','kind':'ai_generated_question'},{'group_id':'c','kind':'ai_generated_question'}]})
            save('stage4.json',{'a':{'status':'eligible'},'b':{'status':'pending'},'c':{'status':'pending'}})
            prompt=write_handoff(folder)['prompt']
            self.assertIn('可用代表1条（关键词1、问句0）',prompt)
            self.assertIn('待确认代表1条',prompt)
            self.assertIn('另有1条去重剔除',prompt)
            self.assertIn('stage4.json',prompt)
            self.assertIn('人工续做/表格/',prompt)

    def test_new_order_handoff_after_sorting_runs_dedup_before_screening(self):
        from handoff import NEW_STAGE_NAMES
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'job.json').write_text(json.dumps({'workflow':'dedup-first','product':{'asin':'OWN'},'max_characters':9000}),encoding='utf-8')
            steps=[{'name':name,'state':'done' if i<2 else 'pending',**({'file':f'{i+1:02d}_{name}.xlsx'} if i<2 else {})} for i,name in enumerate(NEW_STAGE_NAMES)]
            (folder/'status.json').write_text(json.dumps({'steps':steps}),encoding='utf-8')
            result=write_handoff(folder)
            self.assertIn('03 高重合素材去重',result['prompt'])
            self.assertIn('完整包含',result['prompt'])
            copied=(folder/'使用的Skill/listing-material-workflow/SKILL.md').read_text(encoding='utf-8')
            self.assertIn('03高重合素材去重 → 04本品适用性筛选',copied)

    def test_each_stage_points_to_its_required_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            cfg={'workflow':'sorted-first','product':{'asin':'EXAMPLE','raw_details':'完整原文'},'max_characters':9000}
            (folder/'job.json').write_text(json.dumps(cfg),encoding='utf-8')
            for count in range(10):
                steps=[{'name':name,'state':'done' if i<count else 'pending',**({'file':f'{i+1:02d}_{name}.xlsx'} if i<count else {})} for i,name in enumerate(STAGE_NAMES)]
                (folder/'status.json').write_text(json.dumps({'steps':steps}),encoding='utf-8')
                result=write_handoff(folder)
                self.assertEqual(result['next_stage'],count+1 if count<9 else None)
                if count<9:
                    for needed in INPUT_STAGES[count+1]:self.assertIn(steps[needed-1]['file'],result['prompt'])
                self.assertEqual(json.loads((folder/'product.json').read_text(encoding='utf-8')),cfg['product'])
                self.assertTrue((folder/'使用的Skill/listing-material-workflow/references/stages.md').is_file())
                self.assertIn('人工续做',result['prompt'])

    def test_interrupted_stage_is_not_reported_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'job.json').write_text(json.dumps({'product':{},'max_characters':9000}),encoding='utf-8')
            (folder/'status.json').write_text(json.dumps({'steps':[{'state':'done','file':'01.xlsx'},{'state':'running'}]}),encoding='utf-8')
            result=write_handoff(folder)
            self.assertEqual(result['completed'],[1])
            self.assertEqual(result['next_stage'],2)


if __name__=='__main__':unittest.main()
