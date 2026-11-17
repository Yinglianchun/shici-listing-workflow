import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest


SCRIPT=Path(__file__).parent/'skills/listing-material-workflow/scripts/clean_materials.py.txt'
helper=runpy.run_path(str(SCRIPT))


class SkillCleaningTests(unittest.TestCase):
    def test_brand_stripping_preserves_properties_and_originals(self):
        from ad_policy import strip_brand_names
        text='SOJOS polarized aviator sunglasses for women'
        cleaned,removed=strip_brand_names(text,['SOJOS'])
        self.assertEqual(cleaned,'polarized aviator sunglasses for women')
        self.assertEqual(removed,['SOJOS'])
        self.assertEqual(strip_brand_names('VIVIENFANG sunglasses',['SOJOS'])[0],'VIVIENFANG sunglasses')
        rows=[{'Keyword':text,'Type':'关键词'},{'Keyword':'polarized aviator sunglasses for women','Type':'关键词'}]
        result=helper['process'](rows,'strip-brands',['SOJOS'])
        self.assertEqual(result['kept_rows'],1)
        self.assertEqual(result['records'][0]['originals'],rows)
        self.assertIn('polarized',result['records'][0]['row']['Keyword'])
    def test_spelling_order_and_lineage_without_losing_qualifiers(self):
        rows=[{'Keyword':t,'Type':'关键词','ASIN':str(i)} for i,t in enumerate([
            'women sunglasses','sunglasses womens',"women's sunglasses",'women’s sunglasses',
            'gold frame women sunglasses','women sunglasses without case','women sunglasses with case'])]
        result=helper['process'](rows,'dedup')
        self.assertEqual(result['kept_rows'],4)
        merged=next(g for g in result['records'] if len(g['source_rows'])==4)
        self.assertEqual(merged['originals'],rows[:4])
        self.assertEqual(rows[2]['Keyword'],"women's sunglasses")

    def test_questions_and_sheets_are_not_word_bag_merged(self):
        rows=[{'Keyword':t,'Type':'买家问句'} for t in [
            'Do these fit over glasses?', 'Do glasses fit over these?',
            'Can women sunglasses be used for fishing?',
            'Can women sunglasses be used for fishing and golf?']]
        rows.append({**rows[0],'sheet':'other'})
        result=helper['process'](rows,'dedup')
        self.assertEqual(result['kept_rows'],5)
        self.assertFalse(result['semantic_grouping'])

    def test_ad_cleaning_preserves_negation_originals_and_numeric_ambiguity(self):
        rows=[{'Keyword':"women’s sunglasses, gold frame",'Original':"women’s sunglasses, gold frame"},
              {'Keyword':"can't slip, 1,000 g"},{'Keyword':'14,5 cm frame'}]
        result=helper['process'](rows,'ad-a')
        values=[g['row']['Keyword'] for g in result['records']]
        self.assertIn('womens sunglasses gold frame',values)
        self.assertIn('cannot slip 1000 g',values)
        self.assertEqual(len(result['pending']),1)
        self.assertEqual(result['pending'][0]['original']['Keyword'],'14,5 cm frame')
        original=next(g for g in result['records'] if g['row']['Keyword'].startswith('womens'))
        self.assertEqual(original['row']['Original'],rows[0]['Original'])

    def test_standalone_cli_needs_no_repository_imports_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);script=root/'清洗脚本.py.txt';script.write_bytes(SCRIPT.read_bytes())
            source=root/'输入.csv';source.write_text('Keyword,Type\nwomen sunglasses,关键词\nwomens sunglasses,关键词\n',encoding='utf-8')
            original=source.read_bytes();output=root/'结果.json'
            command=[sys.executable,str(script),'--mode','dedup','--input',str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=root,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['kept_rows'],1)
            self.assertEqual(source.read_bytes(),original)
            self.assertNotEqual(subprocess.run(command,cwd=root,capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
