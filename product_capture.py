"""Portable Chrome/Edge capture using their local DevTools protocol; no Node dependency."""
import base64
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


def product_url(value):
    value=value.strip()
    if re.fullmatch(r'[A-Za-z0-9]{10}',value):value='https://www.amazon.com/dp/'+value.upper()
    url=urllib.parse.urlsplit(value)
    if url.scheme!='https' or url.username or url.password or url.port or not re.fullmatch(r'(?:www\.)?amazon\.(?:com|co\.uk|de|fr|it|es|ca|com\.au|co\.jp)',url.hostname or ''):
        raise ValueError('请输入10位ASIN或完整的Amazon商品详情链接')
    match=re.search(r'/(?:dp|gp/product)/([a-zA-Z0-9]{10})(?:/|$)',url.path)
    if not match:raise ValueError('链接中没有找到商品ASIN')
    asin=match[1].upper()
    host=url.hostname if url.hostname.startswith('www.') else 'www.'+url.hostname
    return asin,'https://'+host+'/dp/'+asin


def page_issue(body,html='',url=''):
    if re.search(r'robot check|type the characters|enter the characters|just need to make sure|click the button below to continue shopping',body,re.I) or re.search(r'/errors_page/validateCaptcha',html,re.I):return 'blocked'
    if url.startswith('chrome-error:') or re.search(r'ERR_(?:CONNECTION|TIMED_OUT|NAME_NOT_RESOLVED|PROXY|INTERNET_DISCONNECTED)',body):return 'network_error'
    if re.search(r"(?:sorry.{0,5}we couldn.t find that page|looking for something\?.{0,100}couldn.t find|page not found)",body,re.I|re.S):return 'not_found'
    return None


CAPTURE_MESSAGES={
    'blocked':'Amazon要求访问确认或验证码，尚未进入商品详情页。可点击“重新读取”重试。',
    'network_error':'商品页连接未成功，请检查网络后重新读取。',
    'not_found':'Amazon显示商品页不存在，请核对ASIN或链接。',
    'failed':'页面中未找到商品标题，本次未能读取详情。可重新读取。',
    'asin_mismatch':'页面跳转到了其他ASIN，未回填资料，请核对链接。'}


class DevTools:
    def __init__(self,url):
        url=urllib.parse.urlsplit(url)
        self.socket=socket.create_connection((url.hostname,url.port),timeout=25)
        nonce=base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f'GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        header=b''
        while b'\r\n\r\n' not in header and len(header)<16000:header+=self.exact(1)
        if b' 101 ' not in header:raise RuntimeError('未能连接商品读取浏览器')
        self.sequence=0
    def exact(self,size):
        chunks=[]
        while size:
            part=self.socket.recv(size)
            if not part:raise RuntimeError('商品读取窗口已关闭')
            chunks.append(part);size-=len(part)
        return b''.join(chunks)
    def send(self,data,opcode=1):
        mask=os.urandom(4);length=len(data)
        header=bytes([0x80|opcode,0x80|length]) if length<126 else bytes([0x80|opcode,0x80|126])+struct.pack('!H',length) if length<65536 else bytes([0x80|opcode,0x80|127])+struct.pack('!Q',length)
        self.socket.sendall(header+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def receive(self):
        pieces=[]
        while True:
            first,second=self.exact(2);length=second&127
            if length==126:length=struct.unpack('!H',self.exact(2))[0]
            elif length==127:length=struct.unpack('!Q',self.exact(8))[0]
            mask=self.exact(4) if second&128 else None
            data=self.exact(length)
            if mask:data=bytes(b^mask[i%4] for i,b in enumerate(data))
            opcode=first&15
            if opcode==8:raise RuntimeError('商品读取连接已关闭')
            if opcode==9:self.send(data,10);continue
            if opcode in (0,1):pieces.append(data)
            if first&128 and pieces:return json.loads(b''.join(pieces))
    def call(self,method,params=None):
        self.sequence+=1;identifier=self.sequence
        self.send(json.dumps({'id':identifier,'method':method,'params':params or {}}).encode())
        while True:
            result=self.receive()
            if result.get('id')==identifier:
                if 'error' in result:raise RuntimeError('商品页面读取未完成')
                return result.get('result',{})
    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError('商品页面结构未能读取')
        return result.get('result',{}).get('value')
    def close(self):self.socket.close()


def capture(value,out,on_process=lambda p:None):
    from launcher import browser_executable
    asin,url=product_url(value);folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    browser=browser_executable()
    if not browser:raise ValueError('需要Chrome或Microsoft Edge才能读取详情')
    data=None;process=None;connection=None
    temp_profile=tempfile.TemporaryDirectory(prefix='listing-capture-',ignore_cleanup_errors=True)
    try:
        with temp_profile as profile:
            process=subprocess.Popen([str(browser),'--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--lang=en-US','--disable-extensions','--disable-background-mode','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            on_process(process)
            portfile=Path(profile)/'DevToolsActivePort';deadline=time.monotonic()+12
            while not portfile.exists() and time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('商品读取浏览器未能启动')
                time.sleep(.1)
            if not portfile.exists():raise RuntimeError('商品读取浏览器启动超时')
            port=int(portfile.read_text().splitlines()[0])
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f'http://127.0.0.1:{port}/json/list',timeout=5) as response:targets=json.load(response)
            target=next(t for t in targets if t['type']=='page')
            connection=DevTools(target['webSocketDebuggerUrl']);connection.call('Page.enable')
            navigation=connection.call('Page.navigate',{'url':url});deadline=time.monotonic()+55
            issue='network_error' if navigation.get('errorText') else None
            while time.monotonic()<deadline:
                ready=connection.evaluate("({title:!!document.querySelector('#productTitle'),body:(document.body?.innerText||'').slice(0,6000),challenge:!!document.querySelector('form[action*=validateCaptcha]'),url:location.href})") or {}
                issue=issue or ('blocked' if ready.get('challenge') else page_issue(ready.get('body',''),url=ready.get('url','')))
                if ready.get('title') or issue:break
                time.sleep(.5)
            if not issue:
                connection.evaluate("(async()=>{for(let i=0;i<8;i++){scrollBy(0,900);await new Promise(r=>setTimeout(r,150));}scrollTo(0,0)})()")
                connection.evaluate("(async()=>{for(const id of ['style','features_and_specs']){const body=document.getElementById(id);const button=body?.parentElement?.querySelector('a[aria-expanded=\"false\"]');if(button){button.scrollIntoView({block:'center'});button.click();await new Promise(r=>setTimeout(r,1000));}}scrollTo(0,document.documentElement.scrollHeight);await new Promise(r=>setTimeout(r,1500));scrollTo(0,0)})()")
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    if connection.evaluate("!!document.querySelector('#features_and_specs tr, #style tr, table.voyager-ns-desktop-table tr')"):break
                    time.sleep(.4)
            data=connection.evaluate((Path(__file__).parent/'product-extractor.js').read_text(encoding='utf-8'))
            body=connection.evaluate("document.body?.innerText||''") or ''
            actual=connection.evaluate('location.href')
            html=connection.evaluate('document.documentElement.outerHTML') or ''
            issue=issue or page_issue(body,html,actual)
            try:actual_asin,_=product_url(actual)
            except ValueError:actual_asin=None
            status=issue or ('failed' if not data.get('title') else 'asin_mismatch' if actual_asin!=asin or (data.get('selected_asin') and data['selected_asin']!=asin) else 'partial' if not data.get('bullets') or not data.get('specifications') else 'captured')
            data.update(requested_asin=asin,request_url=url,source_url=actual,page_title=connection.evaluate('document.title'),captured_at=time.strftime('%Y-%m-%d %H:%M:%S'),source_type='listing_claim',status=status,message=CAPTURE_MESSAGES.get(status,''))
            (folder/'page.html').write_text(html,encoding='utf-8')
            (folder/'product.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            return data
    finally:
        if connection:connection.close()
        if process and process.poll() is None:
            try:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                else:process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        temp_profile.cleanup()


def details_text(data):
    parts=[data['title']]
    if data.get('bullets'):parts+=['\n五点描述',*data['bullets']]
    for key,label in [('overview','商品概览'),('specifications','规格参数')]:
        if data.get(key):parts+=['\n'+label,*[p['name']+'：'+p['value'] for p in data[key]]]
    if data.get('description'):parts+=['\n商品描述',data['description']]
    if data.get('aplus_text'):parts+=['\nA+文字',data['aplus_text']]
    return '\n'.join(parts)
