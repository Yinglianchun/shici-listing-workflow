import unittest
from intents import propose_intents


def group(identifier,kind='ai_generated_question',marketplace='US'):
    return {'group_id':identifier,'kind':kind,'marketplace':marketplace,'text':identifier,
            'asins':['OWN' if identifier=='B' else 'COMPETITOR'],'sources':['source-'+identifier]}


def edge(a,b,relation='equivalent',**extra):
    return {'left':a,'right':b,'left_text':a,'right_text':b,'relation':relation,'status':'needs_review','topics':['尺寸与适配'],**extra}


class IntentTests(unittest.TestCase):
    def test_does_not_follow_transitive_chain_beyond_representative(self):
        groups=[group(x) for x in 'ABCD']
        proposals=propose_intents(groups,[edge('A','B'),edge('B','C'),edge('C','D')],['OWN'])
        self.assertEqual(len(proposals),2)
        for proposal in proposals:
            representative=proposal['representative_id']
            members={member['group_id'] for member in proposal['members']}
            if 'D' in members:
                self.assertNotIn('A',members)
            self.assertEqual(len(proposal['representative_relations']),len(members)-1)
        self.assertEqual(sum(p['source_record_count'] for p in proposals),4)

    def test_known_conflict_prevents_joining_despite_common_equivalent_representative(self):
        proposals=propose_intents([group(x) for x in 'ABC'],[edge('A','B'),edge('B','C'),edge('A','C','same_topic')],['OWN'])
        self.assertEqual(len(proposals),2)
        self.assertFalse(any({'A','C'}<={m['group_id'] for m in p['members']} for p in proposals))

    def test_flagged_proposal_remains_separate_until_human_confirmation(self):
        groups=[group(x) for x in 'AB']
        judged=edge('A','B',review_flags=['原文条件不同'])
        self.assertEqual(len(propose_intents(groups,[judged])),2)
        judged.update(status='confirmed',reviewed_relation='equivalent')
        self.assertEqual(len(propose_intents(groups,[judged])),1)

    def test_all_records_and_kinds_kept_when_no_relations(self):
        groups=[group('A'),group('B',kind='keyword'),group('C',marketplace='DE')]
        proposals=propose_intents(groups,[])
        self.assertEqual(len(proposals),3)
        self.assertEqual({p['members'][0]['group_id'] for p in proposals},{'A','B','C'})


if __name__=='__main__':
    unittest.main()
