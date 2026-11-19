import unittest
from ad_policy import strip_group_brands,matched_brand


class AdPolicyTests(unittest.TestCase):
    def test_brand_removal_preserves_remaining_expression_and_source(self):
        groups=[{'group_id':'a','text':'ViewJoy polarized oval sunglasses','sources':['S1']},
                {'group_id':'b','text':'Are view-joy glasses small?','sources':['S2']},
                {'group_id':'c','text':'black lens sunglasses'},
                {'group_id':'d','text':'ViewJoy','sources':['S3']}]
        cleaned=strip_group_brands(groups,['ViewJoy'])
        self.assertEqual([g['text'] for g in cleaned],
                         ['polarized oval sunglasses','Are glasses small?','black lens sunglasses'])
        self.assertEqual(cleaned[0]['original_text'],groups[0]['text'])
        self.assertEqual(cleaned[0]['sources'],['S1'])
        self.assertEqual(groups[0]['text'],'ViewJoy polarized oval sunglasses')

    def test_boundaries_and_explicit_list(self):
        self.assertEqual(matched_brand('View Joy glasses',['ViewJoy']),'ViewJoy')
        self.assertEqual(matched_brand('VIEW.JOY glasses',['ViewJoy']),'ViewJoy')
        self.assertEqual(matched_brand('View—Joy glasses',['ViewJoy']),'ViewJoy')
        self.assertIsNone(matched_brand('overviewjoy glasses',['ViewJoy']))
        self.assertIsNone(matched_brand('oval glasses',[]))


if __name__=='__main__':unittest.main()
