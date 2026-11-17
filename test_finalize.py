import unittest
from finalize import prefix_groups,compose_reviewed,merge_product_reviews


class FinalizeTests(unittest.TestCase):
    def test_copy_review_cannot_change_original_ad_or_product_decision(self):
        original={'g':{'status':'eligible','ad_status':'exclude','ad_reason':'campaign'}}
        reviews=[{'material':{'material_id':'m','member_ids':['g']},'review':{'status':'exclude','reason':'bad cleaned copy','ad_status':'eligible'}}]
        result=merge_product_reviews(original,reviews)
        self.assertEqual(result['g']['status'],'eligible')
        self.assertEqual(result['g']['ad_status'],'exclude')
        self.assertEqual(result['g']['copy_status'],'exclude')
        self.assertNotIn('copy_status',original['g'])

    def test_explicit_product_correction_and_scoped_manual_changes(self):
        original={'g':{'status':'eligible','ad_status':'eligible'}}
        material={'material_id':'m','member_ids':['g']}
        reviews=[{'material':material,'review':{'status':'eligible'}}]
        ad=merge_product_reviews(original,reviews,{'m':{'scope':'ad','status':'exclude'}})['g']
        self.assertEqual((ad['status'],ad['ad_status'],ad['copy_status']),('eligible','exclude','eligible'))
        copy=merge_product_reviews(original,reviews,{'m':{'scope':'copy','status':'exclude'}})['g']
        self.assertEqual((copy['status'],copy['ad_status'],copy['copy_status']),('eligible','eligible','exclude'))
        reviews[0]['review']={'status':'exclude','product_status':'exclude','product_reason':'confirmed wrong material'}
        corrected=merge_product_reviews(original,reviews)['g']
        self.assertEqual(corrected['status'],'exclude')
        self.assertEqual(corrected['reason'],'confirmed wrong material')

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
