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

    def test_excluded_brand_draft_is_archived_not_used_as_buyer_answer(self):
        draft={'qa_id':'a','topic':'fit','question_en':'Are ViewJoy glasses small?','answer_en':'A draft.'}
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':[draft]},{'excluded_brands':['ViewJoy']},'test',Path(d)/'selection.json',lambda *a:({'main_ids':['a'],'aplus_ids':['a']},{}),lambda:'test')
        self.assertEqual(result['qa'],[])
        self.assertEqual(result['aplus_qa'],[])
        self.assertEqual(result['candidate_qa'][0]['question_en'],draft['question_en'])
        self.assertEqual(len(result['excluded_qa']),1)
        tabs={s['name']:s for s in delivery_sheets(result)}
        self.assertIn('已排除QA留档',tabs)

    def test_unused_aplus_brand_does_not_discard_clean_main_qa(self):
        draft={'qa_id':'a','topic':'fit','question_en':'How wide is the frame?','answer_en':'The frame is 140 mm wide.','aplus_answer_en':'ViewJoy draft.'}
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':[draft]},{'excluded_brands':['ViewJoy']},'test',Path(d)/'selection.json',lambda *a:({'main_ids':['a'],'aplus_ids':[]},{}),lambda:'test')
        self.assertEqual(len(result['qa']),1)
        self.assertEqual(result['excluded_qa'],[])

    def test_aplus_subtitle_is_checked_separately_from_main_qa(self):
        draft={'qa_id':'a','topic':'fit','question_en':'How wide is the frame?','answer_en':'The frame is 140 mm wide.','aplus_subtitle_en':'ViewJoy design','aplus_answer_en':'A clean detailed answer.'}
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':[draft]},{'excluded_brands':['ViewJoy']},'test',Path(d)/'selection.json',lambda *a:({'main_ids':['a'],'aplus_ids':['a']},{}),lambda:'test')
        self.assertEqual(len(result['qa']),1)
        self.assertEqual(result['aplus_qa'],[])
        self.assertEqual(result['excluded_qa'][0]['excluded_target'],['A+'])

    def test_clean_aplus_keeps_source_link_when_main_answer_is_filtered(self):
        draft={'qa_id':'a','topic':'fit','question_en':'How wide is the frame?','answer_en':'A ViewJoy draft.','aplus_answer_en':'The frame is 140 mm wide.','covered_question_ids':['q']}
        original={'id':'q','text':'How wide is the frame?','asins':['OWN']}
        with tempfile.TemporaryDirectory() as d:
            result=curate({'qa':[draft],'original_questions':[original]},{'excluded_brands':['ViewJoy']},'test',Path(d)/'selection.json',lambda *a:({'main_ids':['a'],'aplus_ids':['a']},{}),lambda:'test')
        self.assertEqual(result['qa'],[])
        self.assertEqual(len(result['aplus_qa']),1)
        tabs={p['name']:p for p in delivery_sheets(result)}
        self.assertEqual(tabs['原问关联']['rows'][0][0],'a')
        self.assertEqual(tabs['原问关联']['rows'][0][2],['q'])


if __name__=='__main__':unittest.main()
