import unittest
from ordering import rank_groups,deduplicate_similar,active_groups,restore_lineage

def group(i,text,kind='keyword'):
    return {'group_id':i,'text':text,'normalized':text.lower(),'kind':kind,'marketplace':'US','sources':['S'+i],'asins':['OWN']}

def equivalent(a,b):
    return {'left':a['group_id'],'right':b['group_id'],'left_text':a['text'],'right_text':b['text'],'relation':'equivalent','left_unique':[],'right_unique':[]}

class OrderingTests(unittest.TestCase):
    def test_complete_question_coverage_keeps_richer_original_in_either_order(self):
        short=group('a','Are sunglasses suitable for fishing?','ai_generated_question')
        full=group('b','Are sunglasses suitable for fishing and golf?','ai_generated_question')
        other=group('c','Are sunglasses suitable for fishing at night?','ai_generated_question')
        relation={'left':'a','right':'b','relation':'partial_overlap','left_unique':[],
            'right_unique':['golf'],'left_covers_right':False,'right_covers_left':True}
        for groups in [[short,full,other],[full,short,other]]:
            app={g['group_id']:{'status':'eligible'} for g in groups}
            result=deduplicate_similar(groups,[relation],app)
            self.assertCountEqual(result['kept_ids'],['b','c'])
            self.assertEqual(result['representatives']['a'],'b')

    def test_ordering_preserves_all_and_does_not_claim_equivalence(self):
        groups=[group('a','polarized sunglasses'),group('b','sunglasses polarized'),group('c','cleaning cloth')]
        ranked=rank_groups(groups,[[1,0],[1,0],[0,1]])
        self.assertCountEqual([g['group_id'] for g in ranked['groups']],['a','b','c'])
        self.assertEqual([g['sort_order'] for g in ranked['groups']],[1,2,3])
        self.assertTrue(all(p['relation']=='unjudged' for p in ranked['candidates']))

    def test_new_vocabulary_negation_and_direction_survive_bad_equivalent_suggestion(self):
        groups=[group('a','polarized sunglasses'),group('b','sunglasses polarized'),group('c','anti glare polarized sunglasses'),group('d','not polarized sunglasses'),group('e','How fast do sunglasses change?','ai_generated_question'),group('f','Do sunglasses change?','ai_generated_question')]
        app={g['group_id']:{'status':'eligible'} for g in groups}
        result=deduplicate_similar(groups,[equivalent(groups[0],g) for g in groups[1:4]]+[equivalent(groups[4],groups[5])],app)
        self.assertEqual(result['representatives']['b'],'a')
        self.assertTrue(all(i in result['kept_ids'] for i in ['a','c','d','e','f']))

    def test_no_transitive_collapse_or_pending_to_eligible_collapse(self):
        groups=[group('a','polarized sunglasses'),group('b','sunglasses polarized'),group('c','polarized sunglasses')]
        app={g['group_id']:{'status':'eligible'} for g in groups}
        result=deduplicate_similar(groups,[equivalent(groups[0],groups[1]),equivalent(groups[1],groups[2])],app)
        self.assertEqual(result['kept_ids'],['a','c'])
        app['b']['status']='pending'
        result=deduplicate_similar(groups,[equivalent(groups[0],groups[1])],app)
        self.assertIn('b',result['kept_ids'])

    def test_pending_questions_and_original_qa_lineage_survive(self):
        groups=[group('a','How do I clean these sunglasses?','ai_generated_question'),group('b','How can I clean these sunglasses?','ai_generated_question'),group('c','cleaning spray'),group('d','red sunglasses')]
        app={'a':{'status':'pending'},'b':{'status':'pending'},'c':{'status':'pending'},'d':{'status':'exclude'}}
        self.assertEqual([g['group_id'] for g in active_groups(groups,app)],['a','b'])
        rows=[{'member_ids':['a']}]
        qa={'original_questions':[{'id':'b','text':groups[1]['text']}],'qa':[{'answer_en':'Use included cloth.','covered_question_ids':['b']}]}
        restore_lineage(rows,groups[:2],{'a':'a','b':'a'},qa)
        self.assertEqual(len(rows[0]['originals']),2)
        self.assertTrue(rows[0]['qa_used'])

if __name__=='__main__':unittest.main()
