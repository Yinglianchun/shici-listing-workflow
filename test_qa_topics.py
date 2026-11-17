import tempfile
import unittest
from pathlib import Path
from qa_topics import discover_topics
from qa import build_candidates,build_output
from test_ordering import group


class TopicTests(unittest.TestCase):
    def test_output_does_not_attach_ids_from_another_topic_input(self):
        buckets={'清洁':[{'id':'q1','text':'How do I clean them?','asins':[]}],
                 '尺寸':[{'id':'q2','text':'How wide is the frame?','asins':[]}]}
        responses={'清洁':{'qa':[{'answer_en':'Use the supplied cloth.','covered_question_ids':['q1','q2'],'candidate_question_ids':['q2']}]}}
        result=build_output(buckets,responses,{'asin':'OWN'})
        self.assertEqual(result['qa'][0]['covered_question_ids'],['q1'])
        self.assertEqual(result['qa'][0]['candidate_question_ids'],[])

    def test_unclassified_questions_can_supply_multiple_concrete_directions(self):
        buckets={'其他':[{'id':'a','text':'How do I clean them?','asins':[]},{'id':'b','text':'How wide is the frame?','asins':[]}]}
        result=build_output(buckets,{'其他':{'qa':[{'topic':'清洁方法','covered_question_ids':['a']},{'topic':'尺寸适配','covered_question_ids':['b']}]}},{'asin':'OWN'},include_reserve=True)
        self.assertEqual([q['topic'] for q in result['qa']],['清洁方法','尺寸适配'])
    def test_actual_topics_include_cleaning_and_keep_custom_bucket(self):
        g=group('q','How do I clean these glasses?','ai_generated_question')
        calls=[]
        def transport(payload,*args):
            calls.append(payload)
            return {'topics':['清洁方法','尺寸适配']},{}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'topics.json'
            topics=discover_topics([g],{'asin':'OWN'},'model',path,transport,lambda:'test')
            self.assertEqual(topics,['清洁方法','尺寸适配','其他'])
            self.assertEqual(discover_topics([g],{'asin':'OWN'},'model',path,transport,lambda:self.fail('cached')),topics)
            self.assertEqual(len(calls),1)
            buckets=build_candidates([g],{'q':{'topic':'清洁方法'}},[{'source_id':'Sq','file':'source.csv','csv_record':2}],topics=topics)
            self.assertEqual(buckets['清洁方法'][0]['id'],'q')
