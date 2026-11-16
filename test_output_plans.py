import unittest
from output_plans import cleaned_question_sheets,description_sheets,prefix_sheets
from keyword_layout import keyword_sheets
from materials import assemble
from qa import build_output

class OutputTests(unittest.TestCase):
    def test_core_driving_is_not_counted_again_but_other_activities_are(self):
        from grading import compute_level
        a={'core_term':'night driving glasses','attributes':[{'concept':'polarization','values':['polarized']},{'concept':'driving_use','values':['driving']},{'concept':'activity','values':['fishing','golf']}],
           'activity_values':['driving','fishing','golf'],'activity_attribute_concepts':['driving_use','activity']}
        result=compute_level(a,'keyword')
        self.assertEqual(result['level'],3)
        self.assertEqual(len(result['attributes']),2)
        a['core_term']='sunglasses'
        self.assertEqual(compute_level(a,'keyword')['level'],4)

    def test_core_terms_merge_case_variants_and_sum_counts(self):
        gs=[{'group_id':i,'kind':'keyword','text':text,'sources':[],'assessment':{'core_term':core,'level':1,'attributes':[]}} for i,text,core in [('a','women sunglasses','Sunglasses'),('b','men sunglasses','sunglasses')]]
        plans=keyword_sheets(gs,gs,[],{i:{'status':'eligible'} for i in ['a','b']},{'a':'a','b':'b'},{})
        self.assertEqual(len(plans[0]['rows']),1)
        self.assertEqual(plans[0]['rows'][0][:3],['sunglasses','否',2])

    def test_description_is_one_line_and_separator_counts_towards_budget(self):
        text,selected=assemble([{'text':'yellow\nlenses','priority':1,'level':1},{'text':'polarized glasses','priority':1,'level':2}],30)
        self.assertEqual(text,'yellow lenses')
        text,_=assemble([{'text':'yellow\nlenses','priority':1,'level':1},{'text':'polarized glasses','priority':1,'level':2}],100)
        self.assertEqual(text,'yellow lenses; polarized glasses')

    def test_cleaned_levels_only_contain_approved_material(self):
        def row(i,n,status):return {'material':{'material_id':i,'kind':'ai_generated_question','level':n,'text':'Question '+i,'phrase':'phrase '+i,'member_ids':[i]},'review':{'status':status}}
        plans=cleaned_question_sheets([row('bad',1,'exclude'),row('b',5,'eligible'),row('a',4,'eligible')],[])
        self.assertEqual([r[4] for r in plans[-1]['rows']],[4,5])
        self.assertNotIn('bad',str(plans))
        self.assertFalse(any('复核' in p['name'] for p in plans))

    def test_keyword_levels_are_deduped_and_usable(self):
        gs=[{'group_id':i,'kind':'keyword','text':text,'sources':[],'assessment':{'core_term':'sunglasses','level':level,'attributes':[]}} for i,text,level in [('a','women sunglasses',1),('b','sunglasses women',1),('c','bad sunglasses',2)]]
        app={'a':{'status':'eligible'},'b':{'status':'eligible'},'c':{'status':'exclude'}}
        plans=keyword_sheets(gs,gs,[],app,{g['group_id']:g['group_id'] for g in gs},{})
        self.assertEqual(len(plans[1]['rows']),1)
        self.assertNotIn('bad sunglasses',str(plans))
        self.assertEqual(len(plans),5)

    def test_one_qa_per_direction_keeps_original_pool(self):
        buckets={'topic':[{'id':'a','text':'Q1','asins':[]},{'id':'b','text':'Q2','asins':[]}]}
        result=build_output(buckets,{'topic':{'qa':[{'question_en':'Q1','answer_en':'A','covered_question_ids':['a']},{'question_en':'Q2','answer_en':'B'}]}},{'asin':'OWN'})
        self.assertEqual(len(result['qa']),1)
        self.assertEqual(len(result['original_questions']),2)
