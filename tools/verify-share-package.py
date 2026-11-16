"""Smoke-test an extracted share archive without workspace dependencies."""
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

archive=Path(sys.argv[1]).resolve()
SMOKE='''
import json,threading,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
import launcher,workbench_server as server,workbench_worker,group_dedup,output_plans
from excel_export import export_excel
from stage_templates import templates
server.key=lambda:''
http=server.create_server()
thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(http.server_port)
try:
 bootstrap=json.load(urllib.request.urlopen(base+'/api/bootstrap'))
 assert bootstrap['product']['asin']==''
 assert json.load(urllib.request.urlopen(base+'/api/jobs'))==[]
 assert urllib.request.urlopen(base+'/').status==200
 for name in ['app.js','wizard.js','minimal.js','select.js','model-picker.js','run-status.js','figma.css','motion.css']:
  assert urllib.request.urlopen(base+'/'+name).status==200
 assert not Path('tools/xlsx/node_modules').exists()
 count=0
 for name,plans in templates().items():
  target=export_excel(plans,Path('smoke-exports')/name)
  with ZipFile(target) as z:
   assert z.testzip() is None
   for n in z.namelist():
    if n.endswith('.xml') or n.endswith('.rels'):ET.fromstring(z.read(n))
  count+=1
 for name in ['启动工作台.cmd','安装无边框组件.cmd']:
  content=Path(name).read_bytes()
  assert bytes([13,10]) in content and bytes([13,13,10]) not in content
 from workbench_worker import STAGES
 from naming import plan_file
 identifier='a'*32;folder=server.DATA/'portable-smoke';folder.mkdir()
 cfg={'id':identifier,'product':{'asin':'SMOKE','title':'Smoke'},'created':'2026-11-16','llm_model':'test','embedding_model':'test','workflow':'dedup-first','excel_subdir':'表格','export_prefix':'SMOKE_2026-11-16','max_characters':9000,'test':True}
 (folder/'job.json').write_text(json.dumps(cfg),encoding='utf-8')
 table=export_excel(templates()['01_导入与基础去重.xlsx'],folder/'01_导入与基础去重.xlsx')
 assert table.parent.name=='表格' and plan_file(table).parent==folder
 relative=table.relative_to(folder).as_posix()
 steps=[{'name':name,'state':'done' if i==0 else 'pending',**({'file':relative} if i==0 else {})} for i,name in enumerate(STAGES)]
 (folder/'status.json').write_text(json.dumps({'state':'paused','steps':steps}),encoding='utf-8')
 job=json.load(urllib.request.urlopen(base+'/api/job/'+identifier+'?stage=1'))
 assert relative in job['files'] and job['preview']
 assert urllib.request.urlopen(base+'/download/'+identifier+'/'+urllib.parse.quote(relative,safe='')).read()[:2]==b'PK'
 handoff=json.load(urllib.request.urlopen(base+'/api/job/'+identifier+'/handoff'))
 assert relative in handoff['prompt'] and '00本品分析' in handoff['prompt']
 from master_workbook import update_master
 from word_export import export_description
 from qa_delivery import export_qa
 cfg.update(report_mode='single-workbook',dynamic_qa_topics=True)
 (folder/'job.json').write_text(json.dumps(cfg),encoding='utf-8')
 master=update_master(folder,1)
 qa_book=export_qa({'qa':[],'original_questions':[]},folder)
 word=export_description('yellow lenses; metal frame',folder/'SMOKE_description.docx','SMOKE')
 (folder/'internal.txt').write_text('process only',encoding='utf-8')
 steps[0]['file']=master.relative_to(folder).as_posix()
 (folder/'status.json').write_text(json.dumps({'state':'paused','steps':steps}),encoding='utf-8')
 job=json.load(urllib.request.urlopen(base+'/api/job/'+identifier+'?stage=1'))
 assert job['report_mode']=='single-workbook' and 'internal.txt' not in job['files']
 assert word.name in job['files'] and job['preview']
 assert qa_book.relative_to(folder).as_posix() in job['files']
 assert urllib.request.urlopen(base+'/download/'+identifier+'/'+urllib.parse.quote(qa_book.relative_to(folder).as_posix(),safe='')).read()[:2]==b'PK'
 assert urllib.request.urlopen(base+'/download/'+identifier+'/'+word.name).read()[:2]==b'PK'
 handoff=json.load(urllib.request.urlopen(base+'/api/job/'+identifier+'/handoff'))
 assert '素材总表空模板.xlsx' in handoff['prompt']
 print(json.dumps({'bootstrap':'ok','frontend_assets':'ok','portable_excel_templates':count,'launcher_import':'ok','workspace_initially_empty':True,'nested_excel_preview_download':'ok','handoff':'ok'},ensure_ascii=False))
finally:
 http.shutdown();http.server_close();thread.join()
'''
with ZipFile(archive) as z:
    names=z.namelist()
    assert not any(any(part in n.split('/') for part in ['工作区','products','__pycache__','node_modules']) for n in names)
    assert not any(n.endswith(('.sqlite3','.db','.env')) for n in names)
    with tempfile.TemporaryDirectory(prefix='shici-share-smoke-') as temporary:
        z.extractall(temporary)
        subprocess.run([sys.executable,'-X','utf8','-c',SMOKE],cwd=Path(temporary)/'拾词',check=True)
