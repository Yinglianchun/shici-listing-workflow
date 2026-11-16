import unittest
from finalize import negative_candidates
from test_ordering import group


class NegativeCandidateTests(unittest.TestCase):
    def test_low_levels_and_excluded_keywords_but_not_pending_or_qa_value(self):
        groups=[group('a','women sunglasses'),group('b','pink sunglasses'),group('c','fit over glasses'),
                group('d','How do I clean sunglasses?','ai_generated_question'),group('e','Are these readers?','ai_generated_question'),
                group('f','yellow polarized sunglasses')]
        statuses={'a':'eligible','b':'exclude','c':'pending','d':'eligible','e':'exclude','f':'eligible'}
        app={i:{'status':s,'reason':'test','basis':'source'} for i,s in statuses.items()}
        graded=[dict(g,assessment={'level':0 if g['group_id']=='d' else 2 if g['group_id']=='f' else 1,'core_term':'sunglasses'}) for g in groups]
        result=negative_candidates(groups,app,graded,{g['group_id']:g['group_id'] for g in groups})
        texts={r['text'] for r in result}
        self.assertIn('women sunglasses',texts)
        self.assertIn('sunglasses',texts)
        self.assertIn('pink sunglasses',texts)
        self.assertIn('How do I clean sunglasses?',texts)
        self.assertNotIn('fit over glasses',texts)
        self.assertNotIn('Are these readers?',texts)
        self.assertNotIn('yellow polarized sunglasses',texts)
        self.assertEqual(next(r for r in result if r['text']=='sunglasses')['sources'],['Sa','Sf'])
