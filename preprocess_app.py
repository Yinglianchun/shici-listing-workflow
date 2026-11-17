"""Standalone, program-only import/deduplication and optional embedding sorting."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from cleaner import load,deduplicate
from semantic import embed_texts,DEFAULT_MODEL
from ordering import rank_groups
from excel_export import portable_excel
from naming import prefix,today

ROOT=Path(__file__).resolve().parent
FINAL_NAMES=['本品资料与页面改动建议','QA与A+问答','投放分级关键词与问句','描述素材']


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def run_preprocess(folder,embedder=embed_texts):
    folder=Path(folder);cfg=json.loads((folder/'preprocess.json').read_text(encoding='utf-8'))
    stem=cfg['export_prefix'];tables=folder/'过程表格';tables.mkdir(exist_ok=True)
    def progress(message):save(folder/'status.json',{'state':'running','message':message})
    try:
        progress('导入与基础去重')
        sources=load([Path(p) for p in cfg['inputs']]);groups=deduplicate(sources)
        save(folder/'stage1.json',{'sources':sources,'groups':groups})
        headers=['Keyword','原文ID','类型','来源ID','ASIN']
        plans=[{'name':name,'headers':headers,'rows':[[g['text'],g['group_id'],g['kind'],g['sources'],g['asins']] for g in groups if g['kind']==kind]}
               for name,kind in [('关键词','keyword'),('完整问句','ai_generated_question'),('其他类型','unknown')]]
        portable_excel(plans,tables/(stem+'_01_基础去重.xlsx'))
        write_preprocess_handoff(folder,cfg)
        if cfg.get('sort'):
            progress('相似排序：读取embedding')
            vectors,_=embedder([g['text'] for g in groups],ROOT/'工作区/embedding-cache.sqlite3',model=cfg.get('embedding_model') or DEFAULT_MODEL,progress=progress)
            ranked=rank_groups(groups,vectors);save(folder/'stage2.json',ranked)
            portable_excel([
                {'name':'排序分组','headers':['Keyword','相似组','排序','原文ID','比较锚点','类型','来源ID'],
                 'rows':[[g['text'],g['sort_group'],g['sort_order'],g['group_id'],g['sort_anchor'],g['kind'],g['sources']] for g in ranked['groups']]},
                {'name':'相似候选','headers':['左原文','右原文','文字重合度','语义相似度','左原文ID','右原文ID'],
                 'rows':[[p['left_text'],p['right_text'],p['token_overlap'],p['score'] if p['score_type']=='embedding_cosine' else '',p['left'],p['right']] for p in ranked['candidates']]}
            ],tables/(stem+'_02_相似排序.xlsx'))
        write_preprocess_handoff(folder,cfg)
        save(folder/'status.json',{'state':'completed','message':f'已整理{len(sources)}条来源、{len(groups)}组原文。下一步补本品资料并交给AI按Skill续做。','sources':len(sources),'groups':len(groups)})
    except Exception as error:
        save(folder/'status.json',{'state':'failed','message':str(error)})
        raise


def write_preprocess_handoff(folder,cfg):
    stem=cfg['export_prefix']
    skill=folder/'使用的Skill/listing-material-workflow'
    shutil.copytree(ROOT/'skills/listing-material-workflow',skill,dirs_exist_ok=True)
    final=folder/'表格';final.mkdir(exist_ok=True)
    for name in FINAL_NAMES:
        source=skill/'assets'/(name+'空模板.xlsx');target=final/(stem+'_'+name+'.xlsx')
        if not target.exists():shutil.copyfile(source,target)
    prompt=f'''请由当前agent使用listing-material-workflow Skill直接继续项目：{folder}
先读使用的Skill/listing-material-workflow/SKILL.md、references/stages.md和references/applicability-and-advertising.md，再读过程表格及stage1.json完整来源。'''
    prompt+= '\n已完成01基础去重和02文字＋embedding相似排序；stage2.json为完整排序输入，相似组不是重复结论。' if (folder/'stage2.json').exists() else '\n仅完成01基础去重，未计算embedding。先由当前agent按文本与语义组织比较候选，不虚构embedding分数。'
    prompt+='''
本次继续前先补00本品分析：向用户取得本品标题、全部五点、参数、已有QA/A+、主图说明与已确认实物补充，并问清主推子体、框色/片色、部件尺寸、品牌排除和投放策略。本轮若缺00分析，就只完成00并停下；若00已完成，本轮只做03本品适用性筛选。每轮只完成一个步骤，落表、给下一步提示后等用户继续，不连做。后续仅在确认适用且用途范围一致的池里做04语义去重，再汇总各CSV、用户此前/当前清单和参考表的核心词，补泛词并固定口径，再分级和提炼关键表达完成广告词库，然后做独立QA，最后复核与组合描述。补充词标本品资料归纳及依据，不编来源次数。
不启动全流程程序、不运行语义工作流脚本、不调用其他LLM API代跑；可以用文件工具读写、统计、排序及导出Excel；Skill内clean_materials.py.txt仅辅助机械清洗，可由当前AI的代码环境运行，不要求用户电脑安装Python。
在表格里的四份Excel模板逐阶段填结果，原文CSV、JSON、排序与相似候选继续保留。最终交本品资料与页面改动建议、QA与A+问答、投放分级关键词与问句、描述素材四份Excel；更新人工续做/续做记录.md并给下一阶段提示词。QA用卖家口吻。
新Skill的06把所有问句素材提炼成关键表达填投放表Keyword，C列保留完整原问；不按80字符分档，不一律删除for/with等关系词，QA正式问题不清洗。01/02过程表仍是原文，不先改写来源。
'''
    (folder/(stem+'_接下来怎么做.txt')).write_text(prompt,encoding='utf-8')


def main():
    runtime=ROOT/'runtime/tcl'
    if runtime.exists():
        os.environ['TCL_LIBRARY']=str(runtime/'tcl8.6');os.environ['TK_LIBRARY']=str(runtime/'tk8.6')
    import tkinter as tk
    from tkinter import filedialog,messagebox
    (ROOT/'工作区').mkdir(exist_ok=True)
    app=tk.Tk();app.title('拾词 · 预处理');app.configure(bg='white');app.geometry('880x560');app.minsize(840,560)
    app.update_idletasks();app.geometry(f'+{max(0,(app.winfo_screenwidth()-880)//2)}+{max(0,(app.winfo_screenheight()-560)//2)}')
    box=tk.Frame(app,bg='white');box.pack(fill='both',expand=True,padx=48,pady=24)
    tk.Label(box,text='开始整理',font=('SimSun',25),bg='white',fg='#171717').pack(anchor='w',pady=(0,14))
    tk.Label(box,text='① 选择CSV文件',font=('Microsoft YaHei',12),bg='white').pack(anchor='w')
    paths=[];chosen=tk.StringVar(value='尚未选择');tk.Label(box,textvariable=chosen,bg='white',fg='#666666').pack(anchor='w',pady=4)
    def pill(label,command,parent=box):
        canvas=tk.Canvas(parent,width=130,height=36,bg='white',highlightthickness=0,cursor='hand2')
        canvas.create_oval(0,0,36,36,fill='#171717',outline='');canvas.create_rectangle(18,0,112,36,fill='#171717',outline='');canvas.create_oval(94,0,130,36,fill='#171717',outline='')
        canvas.create_text(65,18,text=label,fill='white',font=('Microsoft YaHei',10));canvas.bind('<Button-1>',lambda _:command());return canvas
    def select():
        nonlocal paths
        paths=list(filedialog.askopenfilenames(filetypes=[('CSV','*.csv')]))
        chosen.set(f'已选择 {len(paths)} 份CSV' if paths else '尚未选择')
    pill('选择文件',select).pack(anchor='w')
    row=tk.Frame(box,bg='white');row.pack(fill='x',pady=10)
    tk.Label(row,text='本品ASIN',bg='white').pack(side='left');asin=tk.Entry(row,width=20);asin.pack(side='left',padx=12)
    sorting=tk.BooleanVar(value=False)
    tk.Checkbutton(box,text='② 再做相似排序（仅调用embedding）',variable=sorting,bg='white',activebackground='white',font=('Microsoft YaHei',12)).pack(anchor='w')
    fields=tk.Frame(box,bg='white');fields.pack(fill='x',pady=6)
    tk.Label(fields,text='模型',bg='white').grid(row=0,column=0,sticky='w');model=tk.Entry(fields,width=30);model.insert(0,DEFAULT_MODEL);model.grid(row=0,column=1,padx=10)
    tk.Label(fields,text='Key',bg='white').grid(row=1,column=0,sticky='w',pady=8);key=tk.Entry(fields,width=30,show='•');key.grid(row=1,column=1,padx=10)
    tk.Label(fields,text='仅排序需要；可留空使用本机用户变量',bg='white',fg='#777777').grid(row=1,column=2)
    state=tk.StringVar(value='只做基础去重不需要API。');tk.Label(box,textvariable=state,bg='white',fg='#555555',wraplength=710,justify='left').pack(anchor='w',pady=6)
    process=None;job=None;log=None
    def poll():
        nonlocal log
        if job and (job/'status.json').exists():
            try:state.set(json.loads((job/'status.json').read_text(encoding='utf-8'))['message'])
            except (OSError,ValueError):pass
        if process and process.poll() is None:app.after(400,poll)
        elif log:log.close();log=None
    def start():
        nonlocal process,job,log
        if process and process.poll() is None:return
        if not paths:messagebox.showinfo('选择文件','请先选择CSV。');return
        if not asin.get().strip():messagebox.showinfo('本品ASIN','请填写本品ASIN，用于命名文件。');return
        stem=prefix(asin.get().strip(),today());base=ROOT/'工作区';base.mkdir(exist_ok=True)
        number=1
        while True:
            job=base/(stem+'_预处理'+(f'_{number:02d}' if number>1 else ''))
            try:job.mkdir();break
            except FileExistsError:number+=1
        incoming=job/'input';incoming.mkdir();inputs=[]
        for i,name in enumerate(paths,1):
            target=incoming/(f'{i:02d}_'+Path(name).name);shutil.copyfile(name,target);inputs.append(str(target))
        save(job/'preprocess.json',{'export_prefix':stem,'inputs':inputs,'sort':sorting.get(),'embedding_model':model.get().strip() or DEFAULT_MODEL})
        env=os.environ.copy()
        if key.get().strip():env['SILICONFLOW_API_KEY']=key.get().strip()
        key.delete(0,'end');log=(job/'运行日志.txt').open('w',encoding='utf-8')
        exe=Path(sys.executable).with_name('python.exe')
        process=subprocess.Popen([str(exe),'-X','utf8',str(Path(__file__).resolve()),'--worker',str(job)],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        state.set('正在整理…');app.after(400,poll)
    controls=tk.Frame(box,bg='white');controls.pack(fill='x',pady=4)
    pill('开始',start,controls).pack(side='left')
    pill('打开工作区',lambda:os.startfile(str(job or ROOT/'工作区')),controls).pack(side='left',padx=14)
    def close():
        if process and process.poll() is None:
            process.terminate();process.wait(timeout=10)
            if job:save(job/'status.json',{'state':'stopped','message':'已停止，完成的文件仍在工作区。'})
        if log:log.close()
        app.destroy()
    app.protocol('WM_DELETE_WINDOW',close);app.mainloop()


if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='--worker':run_preprocess(sys.argv[2])
    else:main()
