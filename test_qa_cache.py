import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import qa


class QACacheTests(unittest.TestCase):
    def test_separate_qa_sends_unclassified_excluded_original_to_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'qa'
            def save(name,value):(root/name).write_text(json.dumps(value),encoding='utf-8')
            save('groups.json',[{'group_id':'q','kind':'ai_generated_question','text':'Can these hold prescription lenses?','asins':['OWN'],'sources':['s']}])
            save('sources.json',[{'source_id':'s','file':'input.csv','csv_record':2}])
            save('graded_groups.json',[])
            save('applicability.json',{'q':{'status':'exclude'}})
            save('product.json',{'asin':'OWN'})
            args=['qa.py','--input',str(root),'--assessments',str(root),'--product',str(root/'product.json'),'--out',str(out),'--model','test','--separate-qa']
            response={'qa':[{'topic':'处方兼容性','question_en':'Can these hold prescription lenses?','covered_question_ids':['q']}]}
            with patch('sys.argv',args),patch.object(qa,'read_api_key',return_value='test'),patch.object(qa,'request_json',return_value=(response,{})) as request,patch('qa_delivery.curate',side_effect=lambda result,*a:result):
                qa.main()
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[0][0]['questions'][0]['applicability'],'exclude')
            result=json.loads((out/'qa_selection.json').read_text(encoding='utf-8'))
            self.assertEqual(result['qa'][0]['topic'],'处方兼容性')
            self.assertEqual(len(result['original_questions']),1)

    def test_resume_reuses_only_identical_product_and_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'qa'
            def save(name,value):
                (root/name).write_text(json.dumps(value),encoding='utf-8')
            topic=qa.TOPICS[0]
            question={'group_id':'q','kind':'ai_generated_question','text':'Do lenses change tint?',
                      'asins':['OWN'],'sources':['s']}
            save('groups.json',[question])
            save('sources.json',[{'source_id':'s','file':'input.csv','csv_record':2}])
            save('graded_groups.json',[{'group_id':'q','assessment':{'topic':topic}}])
            save('applicability.json',{'q':{'status':'eligible'}})
            product={'asin':'OWN','title':'First product'}
            save('product.json',product)
            args=['qa.py','--input',str(root),'--assessments',str(root),
                  '--product',str(root/'product.json'),'--out',str(out),'--model','test']
            with patch('sys.argv',args),patch.object(qa,'read_api_key',return_value='test'),patch.object(qa,'request_json',return_value=({'qa':[]},{})) as request:
                qa.main()
                qa.main()
                self.assertEqual(request.call_count,1)
                product['title']='Updated product'
                save('product.json',product);qa.main()
                self.assertEqual(request.call_count,2)
                question['text']='How quickly do lenses change tint?'
                save('groups.json',[question]);qa.main()
                self.assertEqual(request.call_count,3)
                save('applicability.json',{'q':{'status':'pending'}});qa.main()
                self.assertEqual(request.call_count,4)
