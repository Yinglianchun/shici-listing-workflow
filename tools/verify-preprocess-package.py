"""Verify the extracted portable runtime, native form, and preprocessing exports."""
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

SMOKE=r'''
import json,sys,os
from pathlib import Path
import preprocess_app as app
assert Path(sys.prefix).resolve()==(Path.cwd()/'runtime').resolve()
import numpy
assert str(Path.cwd()) in numpy.__file__
job=Path.cwd()/'工作区/OWN_2026-11-16_预处理';job.mkdir(parents=True)
csv=job/'input.csv'
csv.write_text(chr(10).join(['Keyword,Type,ASIN','small sunglasses,关键词,OWN','small sunglasses,关键词,OTHER','How do I clean these sunglasses?,买家问句,OWN']),encoding='utf-8')
cfg={'export_prefix':'OWN_2026-11-16','inputs':[str(csv)],'sort':False}
app.save(job/'preprocess.json',cfg)
def no_api(*a,**kw):raise AssertionError('basic mode made an API call')
app.run_preprocess(job,no_api)
assert len(list((job/'最终输出').glob('*.xlsx')))==4
assert json.loads((job/'status.json').read_text(encoding='utf-8'))['groups']==2
cfg['sort']=True;app.save(job/'preprocess.json',cfg)
app.run_preprocess(job,lambda texts,*a,**kw:([[1,0],[0,1]],{}))
assert (job/'stage2.json').exists()
assert len(list((job/'过程表格').glob('*.xlsx')))==2
assert '先读使用的Skill' in (job/'OWN_2026-11-16_接下来怎么做.txt').read_text(encoding='utf-8')
import tkinter as tk
old_init=tk.Tk.__init__
def hidden_init(self,*a,**kw):old_init(self,*a,**kw);self.withdraw()
def inspect_form(self):
 self.update_idletasks()
 assert self.title()=='拾词 · 预处理'
 assert self.winfo_children()
 assert self.winfo_reqheight()<=560, self.winfo_reqheight()
 self.destroy()
tk.Tk.__init__=hidden_init;tk.Tk.mainloop=inspect_form
app.main()
print(json.dumps({'bundled_runtime':'ok','bundled_numpy':'ok','native_form':'ok','no_api_basic_mode':'ok','optional_sorting':'ok','four_templates':'ok','handoff':'ok'}))
'''

with tempfile.TemporaryDirectory(prefix='shici-preprocess-check-') as temporary:
    with ZipFile(Path(sys.argv[1]).resolve()) as z:
        assert z.testzip() is None
        assert not any('/工作区/' in n or n.endswith('workbench_worker.py') or n.endswith('qa.py') for n in z.namelist())
        z.extractall(temporary)
    root=Path(temporary)/'拾词预处理'
    subprocess.run([str(root/'runtime/python.exe'),'-X','utf8','-c',SMOKE],cwd=root,check=True)
