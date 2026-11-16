import unittest
from finalize import prefix_groups,compose_reviewed


class FinalizeTests(unittest.TestCase):
    def test_qa_used_questions_still_use_cleaned_phrases(self):
        original='What should I use to clean these sunglasses?'
        row={'material_id':'q','kind':'ai_generated_question','level':0,'sources':['s'],
             'qa_used':True,'text':original,'phrase':'use clean sunglasses'}
        result=compose_reviewed([{'material':row,'review':{'status':'eligible'}}])
        self.assertEqual(result['description'],'use clean sunglasses')
        self.assertEqual(result['description_selection'][0]['format'],'清洗短语')
        self.assertEqual(row['text'],original)

    def test_unresolved_how_intent_cannot_bypass_cleaning_via_qa(self):
        row={'material_id':'q','kind':'ai_generated_question','level':0,'sources':['s'],
             'qa_used':True,'text':'How fast do sunglasses change?','phrase':'how fast do sunglasses change'}
        self.assertEqual(compose_reviewed([{'material':row,'review':{'status':'eligible'}}])['description'],'')

    def test_common_prefix_preserves_all_suffixes_and_full_members(self):
        words=['polarized photochromic sunglasses for men driving','polarized photochromic sunglasses for men fishing']
        groups=prefix_groups([{'text':w} for w in words])
        self.assertEqual(len(groups),1)
        self.assertEqual([m['text'] for m in groups[0]['members']],words)
        self.assertIn('driving',groups[0]['text']);self.assertIn('fishing',groups[0]['text'])
        self.assertLess(len(groups[0]['text']),sum(map(len,words)))

    def test_advertising_keywords_stay_whole_and_pending_is_not_composed(self):
        def row(i,text,status):return {'material':{'material_id':i,'kind':'keyword','level':2,'sources':[i],'qa_used':False,'text':text,'phrase':''},'review':{'status':status}}
        a='polarized photochromic sunglasses for men driving';b='polarized photochromic sunglasses for men fishing'
        result=compose_reviewed([row('1',a,'eligible'),row('2',b,'eligible'),row('3','blue light protection','pending')])
        self.assertEqual([r['keyword'] for r in result['advertising_keywords']],[a,b])
        self.assertNotIn('blue light',result['description'])
        self.assertLess(len(result['description']),9000)


if __name__=='__main__':unittest.main()
