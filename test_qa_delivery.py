import json
import tempfile
import unittest
from pathlib import Path
from qa_delivery import curate,delivery_sheets


class QaDeliveryTests(unittest.TestCase):
    def test_rank_ten_keep_backups_and_only_three_aplus_without_rewriting(self):
        candidates=[{'qa_id':f'QA{i:02d}','topic':f'direction {i}','answer_en':'Original '+str(i),'aplus_answer_en':'Detail '+str(i)} for i in range(1,14)]
        requests=[]
        def transport(*args):
            requests.append(args)
            return {'main_ids':[q['qa_id'] for q in reversed(candidates)],'aplus_ids':['QA01','QA02','QA03','QA04']},{}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'selection.json'
            result=curate({'qa':candidates},{'asin':'OWN'},'test',path,transport,lambda:'test')
            self.assertEqual(len(result['qa']),10)
            self.assertEqual(len(result['reserve_qa']),3)
            self.assertEqual(len(result['aplus_qa']),3)
            self.assertEqual(result['qa'][0]['answer_en'],'Original 13')
            self.assertEqual(len(result['candidate_qa']),13)
            curate({'qa':candidates},{'asin':'OWN'},'test',path,transport,lambda:'test')
            self.assertEqual(len(requests),1)
            self.assertEqual(json.loads(path.read_text())['response']['main_ids'][0],'QA13')

    def test_same_direction_does_not_fill_main_slots_twice(self):
        rows=[{'qa_id':'a','topic':'fit'},{'qa_id':'b','topic':'fit'},{'qa_id':'c','topic':'care'}]
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':rows},{},'test',Path(d)/'selection.json',lambda *a:({'main_ids':['a','b','c'],'aplus_ids':[]},{}),lambda:'test')
        self.assertEqual([q['qa_id'] for q in result['qa']],['a','c'])
        self.assertEqual([q['qa_id'] for q in result['reserve_qa']],['b'])

    def test_final_editorial_answers_keep_original_drafts_and_real_counts(self):
        rows=[{'qa_id':'a','topic':'fit','answer_en':'old draft','aplus_answer_en':'old detail'}]
        response={'main_ids':['a'],'aplus_ids':['a'],'finalized_answers':[
            {'qa_id':'a','answer_en':'New answer.','answer_zh':'新答案','aplus_answer_en':'New detail.'}]}
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':rows},{},'test',Path(d)/'selection.json',lambda *a:(response,{}),lambda:'test')
        self.assertEqual(result['qa'][0]['answer_en'],'New answer.')
        self.assertEqual(result['qa'][0]['answer_characters'],11)
        self.assertEqual(result['aplus_qa'][0]['aplus_characters'],11)
        self.assertEqual(result['candidate_qa'][0]['answer_en'],'old draft')

    def test_reserve_questions_exclude_explicitly_irrelevant_but_keep_pending(self):
        result={'qa':[],'original_questions':[
            {'id':'a','text':'pending question','applicability':{'status':'pending'}},
            {'id':'b','text':'irrelevant','applicability':{'status':'exclude'}}]}
        tabs={p['name']:p for p in delivery_sheets(result)}
        self.assertEqual(len(tabs['备选原问']['rows']),1)
        self.assertEqual(tabs['备选原问']['rows'][0][0],'a')
        self.assertEqual(len(tabs['完整原问池']['rows']),2)


if __name__=='__main__':unittest.main()
