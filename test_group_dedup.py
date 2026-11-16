import unittest
from group_dedup import complete_group_batches,deduplicate_groups
from test_ordering import group

class GroupDedupTests(unittest.TestCase):
    def test_model_sees_only_original_text_type_and_mapping_id(self):
        groups=[{**group('a','Are sunglasses UV400?','ai_generated_question'),'sort_group':'s','Level':99,'Intent':'wrong','Evidence':'competitor claim'},
                {**group('b','Do sunglasses provide UV400?','ai_generated_question'),'sort_group':'s','assessment':{'level':0}}]
        def transport(items,*args):
            texts=items[0]['texts']
            self.assertEqual(texts,[{'id':g['group_id'],'kind':g['kind'],'text':g['text']} for g in groups])
            return {'repeat':[],'covered':[]},{}
        result=deduplicate_groups(groups,'test',transport=transport,key_reader=lambda:'test')
        self.assertEqual(result['kept_ids'],['a','b'])

    def test_literal_and_extension_covers_question_across_sort_groups(self):
        groups=[{**group('a','Are these sunglasses imported?','ai_generated_question'),'sort_group':'one'},
            {**group('b','Are these sunglasses imported and sold as one count?','ai_generated_question'),'sort_group':'two'}]
        result=deduplicate_groups(groups,'test',key_reader=lambda:self.fail('No API needed'))
        self.assertEqual(result['kept_ids'],['b'])
        self.assertEqual(result['representatives']['a'],'b')

    def test_negative_extension_is_not_automatically_folded(self):
        groups=[group('a','Are sunglasses polarized?','ai_generated_question'),group('b','Are sunglasses polarized and not UV protected?','ai_generated_question')]
        result=deduplicate_groups(groups,'test',key_reader=lambda:self.fail('No API needed'))
        self.assertCountEqual(result['kept_ids'],['a','b'])

    def test_batch_boundary_never_cuts_a_similarity_group(self):
        groups=[]
        for label,size in [('a',280),('b',35),('c',310)]:
            groups.extend({**group(label+str(i),'text '+str(i)),'sort_group':label} for i in range(size))
        batches=complete_group_batches(groups,300)
        self.assertEqual([sum(map(len,b)) for b in batches],[280,35,310])
        self.assertEqual(sum(len(m) for b in batches for m in b),625)

    def test_keyword_order_is_program_dedup_without_api(self):
        groups=[group('a','women sunglasses'),group('b','sunglasses women')]
        result=deduplicate_groups(groups,'test',key_reader=lambda:self.fail('No API needed'))
        self.assertEqual(result['kept_ids'],['a'])

    def test_covered_question_deleted_but_other_conditions_survive(self):
        groups=[{**group('a','Are sunglasses suitable for fishing?','ai_generated_question'),'sort_group':'s'},
            {**group('b','Are sunglasses suitable for fishing and golf?','ai_generated_question'),'sort_group':'s'},
            {**group('c','Are sunglasses suitable for fishing at night?','ai_generated_question'),'sort_group':'s'}]
        def transport(items,*args):
            return {'repeat':[],'covered':[['a','b'],['c','b']]},{}
        result=deduplicate_groups(groups,'test',transport=transport,key_reader=lambda:'test')
        self.assertCountEqual(result['kept_ids'],['b','c'])

