import unittest
from unittest.mock import patch
from finalize import prefix_groups,compose_reviewed,merge_product_reviews,final_comparison


class FinalizeTests(unittest.TestCase):
    def test_multi_group_keeps_all_material_beyond_9000(self):
        from output_plans import description_sheets
        reviews=[]
        for i in range(120):
            text=f'feature{i} '+('durable material ' * 6)
            reviews.append({'material':{'material_id':str(i),'kind':'keyword','level':2,'sources':[str(i)],
                'qa_used':False,'text':text,'phrase':'','asins':['COMPETITOR']},'review':{'status':'eligible'}})
        result=compose_reviewed(reviews,multi_group=True)
        self.assertGreater(result['description_total_characters'],9000)
        self.assertGreater(len(result['description_groups']),1)
        self.assertEqual({i for r in result['description_selection'] for i in r['material_ids']},{str(i) for i in range(120)})
        for g in result['description_groups']:
            self.assertLessEqual(len(g['description']),9000)
            self.assertEqual(g['description'],'; '.join(r['text'] for r in g['selection']))
            self.assertEqual(g['target_asin'],'')
            self.assertEqual(g['assignment_status'],'待分配')
        plans=description_sheets(result)
        self.assertEqual(len(plans[0]['rows']),len(result['description_groups']))
        self.assertEqual(plans[1]['headers'][-1],'组号')

    def test_group_boundary_and_duplicate_lineage(self):
        from materials import assemble_groups
        def row(text,i):return {'text':text,'priority':1,'level':2,'material_ids':[i]}
        groups,pending=assemble_groups([row('abc',1),row('ABC',2),row('def',3),row('ghi',4)],8)
        self.assertEqual([g['description'] for g in groups],['abc; def','ghi'])
        self.assertEqual(groups[0]['selection'][0]['material_ids'],[1,2])
        self.assertFalse(pending)

    def test_oversized_prefix_is_unpacked_and_long_single_is_retained(self):
        def row(i,text):return {'material':{'material_id':i,'kind':'keyword','level':2,'sources':[i],
            'qa_used':False,'text':text,'phrase':''},'review':{'status':'eligible'}}
        words=['polarized photochromic sunglasses for men driving','polarized photochromic sunglasses for men fishing']
        result=compose_reviewed([row(str(i),t) for i,t in enumerate(words)]+[row('long','x'*100)],50,multi_group=True)
        self.assertEqual({i for r in result['description_selection'] for i in r['material_ids']},{'0','1'})
        self.assertEqual(result['description_unassigned'][0]['material_ids'],['long'])
        self.assertEqual(result['description_unassigned'][0]['text'],'x'*100)

    def test_question_key_expression_can_be_rephrased_without_overwriting_original(self):
        text='How fast do these photochromic sunglasses change tint?'
        original={'material_id':'q','kind':'ai_generated_question','level':1,'sources':['s'],'qa_used':False,
                  'text':text,'originals':[text],'phrase':'how fast do these photochromic sunglasses change tint'}
        expression='photochromic sunglasses tint change speed'
        with patch('finalize.assess',return_value=({'q':{'status':'eligible','key_expression':expression}},{})):
            reviews,_=final_comparison([original],{'asin':'OWN'},'unused','test')
        self.assertEqual(reviews[0]['material']['phrase'],expression)
        self.assertEqual(reviews[0]['material']['text'],text)
        self.assertEqual(reviews[0]['material']['originals'],[text])
        self.assertTrue(original['phrase'].startswith('how fast'))
        self.assertEqual(compose_reviewed(reviews)['description'],expression)

    def test_rephrasing_cannot_reintroduce_an_excluded_brand(self):
        original={'material_id':'q','kind':'ai_generated_question','originals':['Are these frames gold?'],'phrase':'frames gold'}
        with patch('finalize.assess',return_value=({'q':{'status':'eligible','key_expression':'ViewJoy gold frame sunglasses'}},{})):
            reviews,_=final_comparison([original],{'excluded_brands':['ViewJoy']},'unused','test')
        self.assertEqual(reviews[0]['review']['status'],'exclude')
        self.assertEqual(reviews[0]['review']['model_review']['status'],'eligible')
        self.assertEqual(original['phrase'],'frames gold')

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
        self.assertEqual(result['description'],a+'; '+b)
        self.assertEqual([r['text'] for r in result['description_selection']],[a,b])
        self.assertNotIn('blue light',result['description'])
        self.assertLess(len(result['description']),9000)


if __name__=='__main__':unittest.main()
