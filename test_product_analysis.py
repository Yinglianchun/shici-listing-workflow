import json
import tempfile
import unittest
from pathlib import Path
from product_analysis import analyse_product,analysis_sheets


class ProductAnalysisTests(unittest.TestCase):
    def test_unification_notes_are_exported_without_claiming_a_contradiction(self):
        plans=analysis_sheets({'pending_unification':[{'field':'脸型','left_quote':'small faces','right_quote':'small medium faces','reason':'口径不同','suggestion':'确认范围'}]})
        self.assertEqual(plans[1]['rows'][0],['口径待统一：脸型','small faces','small medium faces','口径不同','确认范围'])

    def test_same_input_reuses_analysis_but_product_changes_are_reanalysed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'product_analysis.json';calls=[]
            def transport(items,*args):
                calls.append(items)
                return {'selling_points':[{'item':'金属框','basis':items[0]['product']['raw_details']}]},{}
            product={'asin':'OWN','raw_details':'Metal frame'}
            first=analyse_product(product,'model',path,transport,lambda:'test')
            self.assertEqual(analyse_product(product,'model',path,transport,lambda:'test'),first)
            self.assertEqual(len(calls),1)
            product={**product,'raw_details':'Metal frame, non polarized'}
            second=analyse_product(product,'model',path,transport,lambda:'test')
            self.assertEqual(len(calls),2)
            self.assertEqual(second['product'],product)
            self.assertIn('Metal frame, non polarized',analysis_sheets(second['analysis'])[0]['rows'][0])
            self.assertEqual(json.loads(path.read_text('utf-8'))['product'],product)
