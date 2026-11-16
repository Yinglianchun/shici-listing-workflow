import tempfile
import json
import unittest
from pathlib import Path
from cleaner import deduplicate, load, normalize, phrase, similar_candidates, attach_products


def source(number, text, asin='B0BW8JZ279', kind='ai_generated_question', market='US'):
    return {'source_id': str(number), 'kind': kind, 'raw': {
        'Keyword': text, 'ASIN': asin, 'Marketplace': market, 'Type': '买家问句' if kind == 'ai_generated_question' else '关键词'}}


class CleanerTests(unittest.TestCase):
    def test_negative_contractions_survive_phrase_cleaning(self):
        for text in ["Can't these sunglasses fit over prescription glasses?",
                     "Won’t these sunglasses darken?", "Do these glasses not darken?",
                     "Don't these sunglasses have nose pads?", "Aren't these lenses polarized?"]:
            with self.subTest(text=text):
                cleaned=phrase(text)['text']
                self.assertIn('not',cleaned.split())
                self.assertNotIn("'t",cleaned)
        self.assertIn('fit over',phrase("Can't these sunglasses fit over prescription glasses?")['text'])

    def test_cross_asin_duplicate_retains_sources(self):
        groups = deduplicate([source(1, 'Do these fit?'), source(2, '  DO these fit ?', 'B07W52VH1X')])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['sources']), 2)
        self.assertEqual(len(groups[0]['asins']), 2)

    def test_distinct_dimensions_negations_and_kinds_stay_separate(self):
        records = [source(1, '14.2 cm arms'), source(2, '142 cm arms'), source(3, 'polarized'),
                   source(4, 'non-polarized'), source(5, 'polarized', kind='keyword'), source(6, 'polarized', market='DE')]
        self.assertEqual(len(deduplicate(records)), 6)

    def test_for_removed_only_in_derived_phrase(self):
        raw = 'Are these sunglasses for men?'
        result = deduplicate([source(1, raw)])[0]
        self.assertEqual(result['text'], raw)
        self.assertEqual(result['phrase_candidate']['text'], 'sunglasses men')
        self.assertIn('fit over', phrase('Do these glasses fit over prescription glasses?')['text'])
        self.assertIn('without slipping', phrase('Do these glasses stay without slipping?')['text'])
        self.assertIn('darkening time', phrase('How long do night driving glasses with photochromic lenses take to darken?')['text'])

    def test_similarity_never_merges_different_fit(self):
        groups = deduplicate([source(1, 'Are these sunglasses suitable for small faces?'), source(2, 'Are these sunglasses suitable for large faces?')])
        candidates, _ = similar_candidates(groups)
        self.assertEqual(len(groups), 2)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]['status'], 'needs_review')

    def test_repeated_input_path_loaded_once(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'input.csv'
            file.write_text('Keyword,Type,ASIN\nhello,关键词,B0BW8JZ279\n', encoding='utf-8-sig')
            self.assertEqual(len(load([file, file])), 1)

    def test_product_links_keep_competitor_and_own_facts_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            own = root / 'own.json'
            own.write_text(json.dumps({'requested_asin':'B0BW8JZ279', 'status':'captured'}), encoding='utf-8')
            index = root / 'index.json'
            index.write_text(json.dumps({'products':[
                {'asin':'B0BW8JZ279','marketplace':'US','role':'own','status':'captured','product_json':str(own)},
                {'asin':'B07W52VH1X','marketplace':'US','role':'competitor','status':'failed'}
            ]}), encoding='utf-8')
            records = [source(1,'UV400'),source(2,'UV400',asin='B07W52VH1X'), source(3,'UV400',market='DE')]
            self.assertEqual(attach_products(records,index),1)
            self.assertEqual(records[0]['product_detail']['role'],'own')
            self.assertEqual(records[1]['product_detail']['status'],'failed')
            self.assertNotIn('product_json',records[1]['product_detail'])
            self.assertEqual(records[2]['product_detail']['status'],'not_captured')


if __name__ == '__main__':
    unittest.main()
