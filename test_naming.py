import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from naming import prefix,project_directory,named_file
import workbench_server as server

class NamingTests(unittest.TestCase):
    def test_human_folders_keep_stable_ids_and_avoid_collisions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/('a'*32);old.mkdir();(old/'job.json').write_text('{}')
            new=project_directory(root,'B0BW8JZ279','2026-11-15')
            again=project_directory(root,'B0BW8JZ279','2026-11-15')
            self.assertEqual(new.name,'B0BW8JZ279_2026-11-15_素材整理')
            self.assertEqual(again.name,new.name+'_02')
            (new/'job.json').write_text(json.dumps({'id':'b'*32,'export_prefix':prefix('B0BW8JZ279','2026-11-15')}),encoding='utf-8')
            with patch.object(server,'DATA',root),patch.object(server,'LEGACY',root/'old'):
                self.assertEqual(server.job_folder('a'*32),old)
                self.assertEqual(server.job_folder('b'*32),new)
            file=named_file(new,'01_导入与基础去重.xlsx')
            self.assertEqual(file.name,'B0BW8JZ279_2026-11-15_01_导入与基础去重.xlsx')
            self.assertEqual(named_file(new,file.name),file)
            self.assertTrue(old.exists())

    def test_filename_component_cannot_escape_workspace(self):
        self.assertNotIn('/',prefix('../ASIN:bad','2026-11-15'))
        self.assertNotIn('\\',prefix('..\\ASIN','2026-11-15'))

if __name__=='__main__':unittest.main()
