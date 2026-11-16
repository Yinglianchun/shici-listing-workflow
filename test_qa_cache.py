import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import qa


class QACacheTests(unittest.TestCase):
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
