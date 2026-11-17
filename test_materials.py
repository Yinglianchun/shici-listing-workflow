import unittest
from materials import assemble,build
from cleaner import phrase


class MaterialTests(unittest.TestCase):
    def test_budget_never_pads_or_cuts_an_item(self):
        candidates=[{'text':'yellow lenses','priority':1,'level':1},{'text':'polarized sunglasses','priority':1,'level':1}]
        text,selected=assemble(candidates,20)
        self.assertLessEqual(len(text),20)
        self.assertIn(text,[c['text'] for c in candidates])
        text,_=assemble(candidates,9000)
        self.assertEqual(text.count('yellow lenses'),1)
        self.assertLess(len(text),9000)

    def test_word_overlap_does_not_erase_a_new_combination(self):
        candidates=[{'text':text,'priority':1,'level':1} for text in ['yellow lenses','polarized sunglasses','yellow polarized sunglasses']]
        text,selected=assemble(candidates)
        self.assertEqual(len(selected),3)

    def test_cleaning_preserves_fit_over_and_negation(self):
        self.assertEqual(phrase('Do these sunglasses fit over prescription glasses?')['text'],'sunglasses fit over prescription glasses')
        self.assertEqual(phrase('Are these sunglasses without nose pads?')['text'],'sunglasses without nose pads')
        self.assertEqual(phrase('How should I clean my sunglasses?')['text'],'clean sunglasses')
        self.assertEqual(phrase('How long do these sunglasses take to darken in sunlight?')['text'],'sunglasses darkening time in sunlight')

    def test_unsupported_member_cannot_be_reintroduced_by_a_merge(self):
        groups=[{'group_id':i,'kind':'keyword','text':t,'marketplace':'US','sources':[i],'asins':['OWN']} for i,t in [('A','metal sunglasses'),('B','plastic sunglasses')]]
        a={'A':{'status':'eligible'},'B':{'status':'exclude'}}
        result=build(groups,{'A':{'level':1}},a,[{'left':'A','right':'B'}],{},'OWN',9000)
        self.assertNotIn('plastic',result['description'])
        self.assertEqual(len(result['held_materials']),1)

    def test_qa_usage_follows_original_wording_after_import_ids_change(self):
        groups=[{'group_id':'NEW','kind':'ai_generated_question','text':'Are these sunglasses polarized?','marketplace':'US','sources':['S'],'asins':['OWN']}]
        qa={'original_questions':[{'id':'OLD','text':groups[0]['text']}],
            'qa':[{'answer_en':'Polarized lenses.','covered_question_ids':['OLD']}]}
        result=build(groups,{'NEW':{'level':1}},{'NEW':{'status':'eligible'}},[],qa,'OWN',9000)
        self.assertTrue(result['materials'][0]['qa_used'])
        self.assertEqual(result['description'],'sunglasses polarized')
        self.assertEqual(result['description_selection'][0]['format'],'清洗短语')


if __name__=='__main__':unittest.main()
