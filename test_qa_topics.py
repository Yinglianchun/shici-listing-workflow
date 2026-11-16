import tempfile
import unittest
from pathlib import Path
from qa_topics import discover_topics
from qa import build_candidates
from test_ordering import group


class TopicTests(unittest.TestCase):
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
