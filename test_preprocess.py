import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import preprocess_app as app


class PreprocessTests(unittest.TestCase):
    def test_basic_no_api_optional_embedding_and_preserved_human_template(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);shutil.copytree(app.ROOT/'skills',root/'skills')
            folder=root/'工作区/OWN_2026-11-16_预处理';folder.mkdir(parents=True)
            csv=folder/'input.csv';csv.write_text('Keyword,Type,ASIN\nsmall sunglasses,关键词,OWN\nsmall sunglasses,关键词,OTHER\nHow do I clean these sunglasses?,买家问句,OWN\n',encoding='utf-8')
            cfg={'inputs':[str(csv)],'export_prefix':'OWN_2026-11-16','sort':False}
            app.save(folder/'preprocess.json',cfg)
            with patch.object(app,'ROOT',root):
                app.run_preprocess(folder,lambda *a,**kw:self.fail('basic import must not call embedding'))
                status=json.loads((folder/'status.json').read_text(encoding='utf-8'))
                self.assertEqual((status['sources'],status['groups']),(3,2))
                self.assertEqual(len(list((folder/'表格').glob('*.xlsx'))),4)
                self.assertIn('未计算embedding',(folder/'OWN_2026-11-16_接下来怎么做.txt').read_text(encoding='utf-8'))
                target=next((folder/'表格').glob('*.xlsx'));target.write_bytes(b'human changes')
                cfg['sort']=True;app.save(folder/'preprocess.json',cfg)
                calls=[]
                def embed(texts,*a,**kw):calls.append(texts);return [[1,0],[0,1]],{}
                app.run_preprocess(folder,embed)
                self.assertEqual(len(calls),1)
                self.assertEqual(target.read_bytes(),b'human changes')
                self.assertTrue((folder/'stage2.json').exists())
                self.assertEqual(len(list((folder/'过程表格').glob('*.xlsx'))),2)


if __name__=='__main__':unittest.main()
