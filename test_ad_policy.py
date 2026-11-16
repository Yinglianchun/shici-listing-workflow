import unittest
from ad_policy import apply_brand_exclusions,matched_brand


class AdPolicyTests(unittest.TestCase):
    def test_brand_is_excluded_in_keywords_and_questions_without_destroying_sources(self):
        groups=[{'group_id':'a','text':'ViewJoy oval sunglasses'}, {'group_id':'b','text':'Are view-joy glasses small?'}, {'group_id':'c','text':'black lens sunglasses'}]
        original={g['group_id']:{'status':'eligible'} for g in groups}
        decisions=apply_brand_exclusions(groups,original,{'excluded_brands':['ViewJoy']})
        for i in ('a','b'):
            self.assertEqual(decisions[i]['ad_status'],'exclude')
            self.assertEqual(decisions[i]['copy_status'],'exclude')
        self.assertEqual(decisions['c'],original['c'])
        self.assertEqual(groups[0]['text'],'ViewJoy oval sunglasses')
        self.assertNotIn('ad_status',original['a'])

    def test_boundaries_and_explicit_list(self):
        self.assertEqual(matched_brand('View Joy glasses',['ViewJoy']),'ViewJoy')
        self.assertIsNone(matched_brand('overviewjoy glasses',['ViewJoy']))
        self.assertIsNone(matched_brand('oval glasses',[]))


if __name__=='__main__':unittest.main()
