"""Local-only HTTP surface for the listing workbench."""
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
import uuid
import re
import io
import zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from naming import project_directory,prefix,today,named_file

ROOT=Path(__file__).parent.resolve()
DATA=ROOT/'工作区'
LEGACY=ROOT/'output/workbench'
WEB=ROOT/'web'
PROCESSES={}
CAPTURES={}
API_KEY=''
SETTINGS={'llm_model':'deepseek-ai/DeepSeek-V4.1-Flash','embedding_model':'BAAI/bge-m3'}


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,data):
    p=Path(p);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)
def key():
    if API_KEY:return API_KEY
    from semantic import read_api_key
    try:return read_api_key()
    except (RuntimeError,OSError):return ''
def stop_process(process):
    if process.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    else:process.terminate()
def stop_jobs():
    for item in list(CAPTURES.values()):
        process=item.get('process')
        if process:stop_process(process)
    for identifier,process in list(PROCESSES.items()):
        if process.poll() is None:
            stop_process(process)
            folder=job_folder(identifier)
            if (folder/'status.json').exists():
                status=read(folder/'status.json');status.update(state='stopped',ended_at=time.time(),error='窗口关闭或已停止；结果已保留，可再次继续。');save(folder/'status.json',status)
                from handoff import write_handoff
                write_handoff(folder)
def job_folder(identifier):
    if not identifier or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('项目不存在')
    folder=DATA/identifier
    if not (folder/'job.json').exists():folder=LEGACY/identifier
    if not (folder/'job.json').exists():
        folder=next((p for p in DATA.iterdir() if p.is_dir() and (p/'job.json').is_file() and read(p/'job.json').get('id')==identifier),None)
        if folder is None:raise ValueError('项目不存在')
    return folder
def launch_job(identifier,until=9,compose=False):
    if until not in range(1,10):raise ValueError('请选择处理到哪个阶段')
    folder=job_folder(identifier)
    if identifier in PROCESSES and PROCESSES[identifier].poll() is None:raise ValueError('这个项目正在处理')
    cfg=read(folder/'job.json');cfg['until']=until;save(folder/'job.json',cfg)
    env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',LISTING_LLM_MODEL=cfg['llm_model'])
    if key():env['SILICONFLOW_API_KEY']=key()
    if cfg.get('topics'):env['LISTING_TOPICS']=json.dumps(cfg['topics'],ensure_ascii=False)
    args=[sys.executable,str(ROOT/'workbench_worker.py'),'--job',str(folder),'--until',str(until)]
    if compose:args.append('--compose-only')
    status=read(folder/'status.json');status['state']='running';status['error']='';status['started_at']=time.time()
    status.pop('ended_at',None);save(folder/'status.json',status)
    with (folder/'process.log').open('a',encoding='utf-8') as log:
        if Path(args[0]).name.lower()=='pythonw.exe':args[0]=str(Path(args[0]).with_name('python.exe'))
        PROCESSES[identifier]=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
def public_job(identifier,stage=None,search=''):
    folder=job_folder(identifier);cfg=read(folder/'job.json');status=read(folder/'status.json')
    process=PROCESSES.get(identifier)
    if status.get('state')=='running' and (not process or process.poll() is not None):
        status['state']='failed';status['error']='处理进程已结束；已完成的表格仍可下载。';save(folder/'status.json',status)
    result={'id':identifier,'title':cfg['product']['title'],'asin':cfg['product']['asin'],'created':cfg['created'],
        'report_mode':cfg.get('report_mode','stage-files'),
        'llm_model':cfg['llm_model'],'embedding_model':cfg['embedding_model'],'status':status,'until':cfg.get('until',9),'workspace':str(folder.resolve()),'export_prefix':cfg.get('export_prefix',''),
        'files':[p.relative_to(folder).as_posix() for base in [folder,folder/'表格'] if base.exists() for p in base.iterdir() if p.is_file() and p.suffix in (('.xlsx','.docx') if cfg.get('report_mode')=='single-workbook' else ('.xlsx','.csv','.txt'))],
        'preview':[]}
    log_path=folder/'process.log'
    if status.get('state')=='running' and log_path.exists():
        tail=log_path.read_bytes()[-12000:].decode('utf-8',errors='replace')
        stage_text=tail.rsplit('阶段 ',1)[-1]
        matches=re.findall(r'(\d+)/(\d+)',stage_text)
        if len(matches)>1:result['progress']={'done':int(matches[-1][0]),'total':int(matches[-1][1])}
    if stage:
        file=status['steps'][int(stage)-1].get('file')
        from naming import plan_file
        plan=plan_file(folder/file) if file else None
        plans=[plan] if plan and plan.exists() else list(folder.glob(f'{cfg.get("export_prefix", "")+"_" if cfg.get("export_prefix") else ""}{int(stage):02d}_*.plan.json'))
        if plans:
            from excel_export import presentation_sheets
            for plan in presentation_sheets(read(plans[0]),translate=False):
                rows=plan['rows']
                if search:rows=[r for r in rows if search.casefold() in json.dumps(r,ensure_ascii=False).casefold()]
                result['preview'].append({**plan,'total':len(rows),'source_total':len(plan['rows']),'rows':rows[:300]})
        elif int(stage)==7 and (folder/'stage7.json').exists():
            reviews=read(folder/'stage7.json')
            result['preview']=[{'name':'合并前自查','headers':['素材ID','原文','建议','原因'],'rows':[[r['material']['material_id'],r['material']['text'],r['review'].get('status'),r['review'].get('reason')] for r in reviews],'total':len(reviews)}]
    if (folder/'stage9.json').exists():result['description']=read(folder/'stage9.json')['description']
    if stage and int(stage)==7 and (folder/'review_decisions.json').exists():
        decisions=read(folder/'review_decisions.json')
        for plan in result['preview']:
            if len(plan['headers'])>4 and plan['headers'][4] not in ('复核建议','自查建议','复核结果'):continue
            for row in plan['rows']:
                if row[0] in decisions:
                    index=4 if len(row)>4 else 2
                    row[index]=decisions[row[0]]['status'];row[index+1]=decisions[row[0]]['reason']
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,value,code=200):
        content=json.dumps(value,ensure_ascii=False).encode('utf-8');self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def local_request(self):
        port=self.server.server_port
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:raise ValueError('请从本机工作台窗口访问')
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://{h}' for h in allowed}:raise ValueError('请从本机工作台窗口操作')
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>50_000_000:raise ValueError('本次上传过大，请分批导入')
        return json.loads(self.rfile.read(length)) if length else {}
    def file(self,path,download=False):
        content=Path(path).read_bytes();self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        if download:self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+urllib.parse.quote(Path(path).name))
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def do_GET(self):
        try:
            self.local_request();url=urllib.parse.urlsplit(self.path);parts=url.path.strip('/').split('/');query=urllib.parse.parse_qs(url.query)
            if url.path=='/api/bootstrap':
                example=ROOT/'products/B0BW8JZ279.json'
                product=read(example) if example.is_file() else {'asin':'','title':'','raw_details':'','facts':{},'core_candidates':[],'pending_questions':[]}
                return self.send({'settings':SETTINGS,'has_key':bool(key()),'product':product})
            if url.path=='/api/jobs':
                folders=list(DATA.iterdir())+(list(LEGACY.iterdir()) if LEGACY.exists() else [])
                return self.send([public_job(read(p/'job.json').get('id',p.name)) for p in sorted(folders,key=lambda p:p.stat().st_mtime,reverse=True) if p.is_dir() and (p/'job.json').exists() and not read(p/'job.json').get('test')])
            if url.path=='/favicon.ico':
                self.send_response(204);self.end_headers();return
            if url.path=='/api/models':
                if not key():raise ValueError('请先填写硅基流动 API Key')
                result={}
                from semantic import NoRedirect
                opener=urllib.request.build_opener(NoRedirect)
                for kind in ['chat','embedding']:
                    request=urllib.request.Request('https://api.siliconflow.cn/v1/models?sub_type='+kind,headers={'Authorization':'Bearer '+key()})
                    try:
                        with opener.open(request,timeout=20) as response:data=json.load(response)
                    except Exception:raise ValueError('未能获取模型列表，请检查密钥或网络；也可以手动填写模型 ID。') from None
                    result[kind]=sorted(r['id'] for r in data.get('data',[]) if isinstance(r.get('id'),str))
                return self.send(result)
            if len(parts)==3 and parts[:2]==['api','capture']:
                item=CAPTURES.get(parts[2])
                if not item:raise ValueError('没有找到这次读取')
                return self.send({k:v for k,v in item.items() if k!='process'})
            if len(parts)==3 and parts[:2]==['api','job']:return self.send(public_job(parts[2],query.get('stage',[None])[0],query.get('q',[''])[0]))
            if len(parts)==4 and parts[:2]==['api','job'] and parts[3]=='handoff':
                from handoff import write_handoff
                return self.send(write_handoff(job_folder(parts[2])))
            if len(parts)>=3 and parts[0]=='download':
                folder=job_folder(parts[1]);path=(folder/urllib.parse.unquote('/'.join(parts[2:]))).resolve()
                if not path.is_relative_to(folder.resolve()) or path.suffix not in ('.xlsx','.csv','.txt','.docx'):raise ValueError('文件不可下载')
                return self.file(path,True)
            if url.path=='/skill':
                buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                    source=ROOT/'skills/listing-material-workflow'
                    names=['SKILL.md']+[p.relative_to(source).as_posix() for base,pattern in [('references','*.md'),('assets','*.xlsx')] for p in sorted((source/base).glob(pattern))]
                    for name in names:archive.write(source/name,'listing-material-workflow/'+name)
                content=buffer.getvalue();self.send_response(200);self.send_header('Content-Type','application/zip')
                self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+urllib.parse.quote('商品拓词流程_Skill.zip'))
                self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
            path=WEB/('index.html' if url.path=='/' else url.path.lstrip('/'))
            if not path.resolve().is_relative_to(WEB.resolve()):raise ValueError('找不到页面')
            return self.file(path)
        except Exception as error:self.send({'error':str(error) if isinstance(error,(ValueError,FileNotFoundError)) else '当前操作未完成，请稍后重试。'},400)
    def do_POST(self):
        global API_KEY
        try:
            self.local_request();data=self.body();parts=urllib.parse.urlsplit(self.path).path.strip('/').split('/')
            if parts==['api','settings']:
                if data.get('api_key'):API_KEY=data['api_key'].strip()
                for k in ['llm_model','embedding_model']:
                    if data.get(k):SETTINGS[k]=str(data[k]).strip()
                save(DATA/'settings.json',SETTINGS)
                return self.send({'settings':SETTINGS,'has_key':bool(key())})
            if parts==['api','capture']:
                from product_capture import product_url,capture,details_text
                asin,url=product_url(str(data.get('input','')))
                identifier=uuid.uuid4().hex;item={'state':'running','asin':asin,'url':url};CAPTURES[identifier]=item
                def work():
                    try:
                        result=capture(url,DATA/'captures'/identifier,on_process=lambda p:item.update(process=p))
                        item.update(state='completed',result=result,details=details_text(result) if result.get('title') else '')
                    except Exception as error:item.update(state='failed',error=str(error))
                threading.Thread(target=work,daemon=True).start()
                return self.send({'id':identifier,'state':'running'})
            if parts==['api','jobs']:
                from workbench_worker import STAGES
                p=data.get('product',{})
                if not p.get('asin') or not p.get('details'):raise ValueError('请填写本品ASIN和详细资料')
                identifier=uuid.uuid4().hex;date=today();folder=project_directory(DATA,p['asin'],date);inputs=folder/'input';inputs.mkdir()
                files=[]
                for index,f in enumerate(data.get('files',[])):
                    name=Path(f['name']).name
                    if not name.lower().endswith('.csv'):raise ValueError('请选择CSV文件')
                    path=inputs/f'{index:02d}_{name}';path.write_text(f['content'],encoding='utf-8',newline='');files.append(str(path.resolve()))
                if not files:raise ValueError('请至少选择一份CSV')
                p=data.get('product',{})
                if not p.get('asin') or not p.get('details'):raise ValueError('请填写本品ASIN和详细资料')
                product={'asin':p['asin'].strip().upper(),'marketplace':'US','title':p.get('title',''),
                    'raw_details':p['details'],'facts':{'用户提供的完整详情':p['details']},'source_type':'manual',
                    'core_candidates':[s.strip() for s in p.get('core_terms','').split(',') if s.strip()],
                    'pending_questions':[s for s in p.get('pending','').splitlines() if s.strip()]}
                if p.get('capture_source'):
                    product['captured_listing']=p['capture_source'];product['source_type']='listing_claim_with_user_details'
                cfg={'id':identifier,'export_prefix':prefix(product['asin'],date),'created':time.strftime('%Y-%m-%d %H:%M'),'inputs':files,'product':product,'test':data.get('test') is True,
                    'llm_model':data.get('llm_model') or SETTINGS['llm_model'],'embedding_model':data.get('embedding_model') or SETTINGS['embedding_model'],
                    'max_characters':max(1,min(int(data.get('max_characters',9000)),50000)),'workflow':'dedup-first',
                    'excel_subdir':'表格','analyze_product':True,'report_mode':'single-workbook','dynamic_qa_topics':True,
                    'fixed_negative_phrases':[s.strip() for s in p.get('negative_phrases','').splitlines() if s.strip()],
                    'topics':[s.strip() for s in p.get('topics','').splitlines() if s.strip()],'until':int(data.get('until',1))}
                save(folder/'job.json',cfg);save(folder/'status.json',{'state':'pending','steps':[{'name':s,'state':'pending'} for s in STAGES]})
                launch_job(identifier,int(data.get('until',9)))
                return self.send(public_job(identifier))
            if len(parts)==4 and parts[:2]==['api','job']:
                identifier=parts[2];folder=job_folder(identifier);action=parts[3]
                if action=='run':launch_job(identifier,int(data.get('until',9)),bool(data.get('compose_only')))
                elif action=='stop':
                    if identifier in PROCESSES:stop_process(PROCESSES[identifier])
                    status=read(folder/'status.json');status.update(state='stopped',ended_at=time.time(),error='已停止，完成的表格仍然保留。');save(folder/'status.json',status)
                    from handoff import write_handoff
                    write_handoff(folder)
                elif action=='open-folder':
                    if os.name!='nt':raise ValueError('请按页面显示的路径打开文件夹')
                    os.startfile(str(folder.resolve()))
                elif action=='decision':
                    path=folder/'review_decisions.json';decisions=read(path) if path.exists() else {}
                    decisions[str(data['material_id'])]={'status':data['status'],'reason':data.get('reason','人工修改'),'decision_source':'manual'};save(path,decisions)
                else:raise ValueError('不支持的操作')
                return self.send(public_job(identifier))
            if parts==['api','clipboard']:
                if not hasattr(self.server,'copy_text'):raise ValueError('请手动复制文本')
                self.server.copy_text(str(data.get('text','')))
                return self.send({'ok':True})
            if parts==['api','shutdown']:
                self.send({'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
            raise ValueError('找不到操作')
        except Exception as error:self.send({'error':str(error) if isinstance(error,ValueError) else '操作未完成，已保存的结果不会丢失。'},400)


def create_server(port=0):
    DATA.mkdir(parents=True,exist_ok=True)
    if not (DATA/'settings.json').exists() and (LEGACY/'settings.json').exists():save(DATA/'settings.json',read(LEGACY/'settings.json'))
    if (DATA/'settings.json').exists():SETTINGS.update(read(DATA/'settings.json'))
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':
    server=create_server(8765)
    print(f'http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    finally:stop_jobs();server.server_close()
