import runpy
import unittest
from pathlib import Path

from excel_export import delivery_sheets, presentation_sheets
from stage_templates import templates


class DeliveryLayoutTests(unittest.TestCase):
    def test_removed_columns_do_not_shift_remaining_values(self):
        source=[{'name':'2级-关键词','headers':['Keyword','Level(源表)','出现ASIN数','涉及ASIN','属性数','建议'],
                 'rows':[['gold sunglasses',4,2,['A','B'],1,'保留']], 'column_widths':[40,12,16,24,10,16]}]
        result=delivery_sheets(source,'投放分级关键词与问句.xlsx')
        self.assertEqual(result[0]['name'],'使用说明')
        self.assertEqual(result[1]['headers'],['Keyword','属性数','建议'])
        self.assertEqual(result[1]['rows'],[['gold sunglasses',1,'保留']])
        self.assertEqual(result[1]['column_widths'],[40,10,16])
        self.assertEqual(len(source[0]['headers']),6)
        self.assertEqual(len(delivery_sheets(result,'投放分级关键词与问句.xlsx')),2)

    def test_all_four_templates_keep_the_guide_first_and_form_fillable(self):
        plans=templates()
        names=['本品资料与页面改动建议空模板.xlsx','QA与A+问答空模板.xlsx','投放分级关键词与问句空模板.xlsx','描述素材空模板.xlsx']
        for name in names:
            shown=presentation_sheets(delivery_sheets(plans[name],name))
            self.assertEqual(shown[0]['name'],'使用说明')
            self.assertTrue(shown[0]['rows'])
            self.assertTrue(all(len(row)==len(s['headers']) for s in shown for row in s['rows']))
        form=next(p for p in plans[names[0]] if p['name']=='确认表单')
        self.assertTrue(any(r[0]=='补充核心泛词' for r in form['rows']))
        self.assertTrue(all(len(r)==4 for r in form['rows']))
        self.assertEqual(form['headers'][-1],'所属大块')
        self.assertEqual(next(r for r in form['rows'] if r[0]=='广告范围与品牌')[-1],'第二块')
        self.assertEqual(next(r for r in form['rows'] if r[0]=='QA使用入口')[-1],'第三块')
        self.assertEqual(next(r for r in form['rows'] if r[0]=='描述分配')[-1],'第四块')

    def test_core_extraction_does_not_promote_keywords_or_count_words(self):
        helper=runpy.run_path(str(Path(__file__).parent/'skills/listing-material-workflow/scripts/clean_materials.py.txt'))
        result=helper['extract_cores']([
            {'CoreTerm':"women's sunglasses",'Category':'sunglasses','Keyword':'beach vacation sunglasses'},
            {'CoreTerm':'womens sunglasses','source_file':'latest.csv'},
            {'CoreTerm':'["beach vacation sunglasses"]'},
        ])
        self.assertEqual([r['term'] for r in result['core_candidates']],["women's sunglasses",'sunglasses','beach vacation sunglasses'])
        self.assertFalse(result['confirmed'])
        empty=helper['extract_cores']([{'Keyword':'not a declared core'}])
        self.assertFalse(empty['core_fields_found'])
        self.assertEqual(empty['core_candidates'],[])


if __name__=='__main__':unittest.main()
