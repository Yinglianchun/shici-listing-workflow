import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
from master_workbook import blank_master_sheets,build_master
from word_export import export_description
from excel_export import portable_excel


class MasterWorkbookTests(unittest.TestCase):
    def test_copy_rejection_is_not_reported_as_product_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            files={'job.json':{'report_mode':'four-workbooks','product':{'asin':'OWN'}},
                'stage1.json':{'sources':[],'groups':[{'group_id':'g','text':'lightweight metal sunglasses','kind':'keyword','sources':[],'asins':[]}]},
                'stage3.json':{'kept_ids':['g']},
                'stage4.json':{'g':{'status':'eligible','ad_status':'eligible','basis':'confirmed'}},
                'stage5.json':[{'group_id':'g','text':'lightweight metal sunglasses','kind':'keyword','sources':[],'asins':[],'assessment':{'level':2,'core_term':'sunglasses','attributes':[]}}],
                'stage7.json':[{'material':{'material_id':'m','member_ids':['g']},'review':{'status':'exclude','reason':'not selected for description'}}]}
            for name,value in files.items():(root/name).write_text(json.dumps(value),encoding='utf-8')
            tabs={p['name']:p for p in build_master(root)}
            self.assertEqual(len(tabs['2级-关键词']['rows']),1)
            self.assertEqual(tabs['已剔除-附原因']['rows'],[])

    def test_blank_template_has_reference_columns_without_old_product_data(self):
        plans=blank_master_sheets()
        self.assertTrue(all(not p['rows'] for p in plans))
        tabs={p['name']:p for p in plans}
        self.assertEqual(tabs['2级-问句']['headers'][:4],['Keyword','长度','原问句','处理'])
        self.assertEqual(tabs['2级-问句']['header_row'],4)
        self.assertEqual(tabs['词组否定']['header_row'],2)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'template.xlsx';portable_excel(plans,path)
            with ZipFile(path) as z:
                for name in z.namelist():
                    if name.endswith('.xml'):ET.fromstring(z.read(name))
                text=z.read('xl/worksheets/sheet2.xml').decode()
                self.assertIn('ref="A4:',text)
                self.assertNotIn('87247E',text)

    def test_fixed_phrase_and_model_suggestion_remain_distinguishable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'job.json').write_text(json.dumps({'product':{'asin':'OWN'},'fixed_negative_phrases':['reading glasses']}),encoding='utf-8')
            (root/'product_analysis.json').write_text(json.dumps({'analysis':{'negative_directions':[
                {'phrase':'small','status':'not_recommended','reason':'small-face product'},
                {'phrase':'polarized','status':'pending','reason':'variant to confirm'},
                {'phrase':'reading glasses','status':'recommended','reason':'different product'}]}}),encoding='utf-8')
            tabs={p['name']:p for p in build_master(root)}
            self.assertEqual(len(tabs['词组否定']['rows']),1)
            self.assertEqual(tabs['词组否定']['rows'][0][-1],'已确认')
            self.assertEqual(len(tabs['否定方向建议']['rows']),3)

    def test_word_has_intact_description_in_a_single_body_paragraph(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'description.docx';text='yellow lenses; metal frame & UV400'
            export_description(text,path,'OWN')
            with ZipFile(path) as z:
                root=ET.fromstring(z.read('word/document.xml'))
                ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                paragraphs=root.findall('w:body/w:p',ns)
                self.assertEqual(''.join(paragraphs[-1].itertext()),text)
                for name in z.namelist():
                    if name.endswith('.xml') or name.endswith('.rels'):ET.fromstring(z.read(name))
