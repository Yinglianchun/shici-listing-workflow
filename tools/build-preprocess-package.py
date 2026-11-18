"""Create a portable Windows preprocessing package with its Python runtime."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime
import ast

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/01a1d4ae-2cd3-7ac0-9232-a9932a740270'
PYTHON=Path('C:/Python313')
target=OUT/('拾词_预处理独立版_'+datetime.now().strftime('%Y-%m-%d')+'.zip')
excluded={'site-packages','__pycache__','test','tests','idlelib','ensurepip','turtledemo','venv'}
modules=['preprocess_app.py','cleaner.py','semantic.py','ordering.py','excel_export.py','table_layout.py','naming.py']
for name in modules:ast.parse((ROOT/name).read_text(encoding='utf-8'),filename=name)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for name in modules:
        z.write(ROOT/name,'拾词预处理/'+name)
    for p in (ROOT/'skills/listing-material-workflow').rglob('*'):
        if p.is_file() and (p.suffix in ('.md','.xlsx','.yaml') or (p.suffix=='.txt' and 'scripts' in p.relative_to(ROOT/'skills/listing-material-workflow').parts)):
            z.write(p,'拾词预处理/skills/listing-material-workflow/'+p.relative_to(ROOT/'skills/listing-material-workflow').as_posix())
    for name in ['python.exe','pythonw.exe','python313.dll','python3.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt']:
        z.write(PYTHON/name,'拾词预处理/runtime/'+name)
    for directory in ['Lib','DLLs','tcl']:
        for p in (PYTHON/directory).rglob('*'):
            relative=p.relative_to(PYTHON)
            if p.is_file() and p.suffix not in ('.pyc','.pyo') and not set(relative.parts)&excluded:
                z.write(p,'拾词预处理/runtime/'+relative.as_posix())
    for directory in (PYTHON/'Lib/site-packages').glob('numpy*'):
        if not directory.is_dir():continue
        for p in directory.rglob('*'):
            if p.is_file() and p.suffix not in ('.pyc','.pyo') and not set(p.relative_to(directory).parts)&{'__pycache__','tests','test'}:
                z.write(p,'拾词预处理/runtime/Lib/site-packages/'+p.relative_to(PYTHON/'Lib/site-packages').as_posix())
    z.writestr('拾词预处理/runtime/python313._pth','Lib\nLib/site-packages\nDLLs\n.\n..\n')
    z.writestr('拾词预处理/启动预处理.cmd','@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0preprocess_app.py"\r\n'.encode('utf-8'))
    z.writestr('拾词预处理/使用说明.txt','''完整解压后双击“启动预处理.cmd”。已包含Python运行环境，不需要安装Python。
选择CSV并填写本品ASIN。默认只做导入和基础去重，不用API；可勾选相似排序，使用硅基流动embedding（默认BAAI/bge-m3）。Key可临时填写或使用本机用户变量，不写入文件。
程序不会调用生成式LLM，不会做本品适用性、语义去重、分级或写QA。关闭窗口会停止本次任务，已经完成的文件仍保留。
结果在程序目录的工作区/ASIN_日期_预处理。过程表格保存基础去重及可选排序，相似组不是重复结论；原始CSV与完整JSON保留。
项目内“表格”预放四份空模板，供AI按Skill逐阶段填写。复制“接下来怎么做.txt”的提示词，把项目交给能读写文件的AI；网页版AI需要上传相应文件，本机路径本身不能被网页AI读取。
AI按四块继续：本品资料、投放分级词句、QA与A+、描述素材。每块先读取已有资料、给补充表单，补齐后发“1”执行该块。先补00本品分析；未做02时先补比较候选，再做03本品适用性、04高重合去重，不能跳过适用性。块内顺序执行，完成后停在下一块表单；最终只交四份Excel，不另写续做日志。
工作区/embedding-cache.sqlite3为本机向量缓存；分享程序请使用原始干净压缩包，避免把自己的工作区一起发出。
'''.encode('utf-8'))
with ZipFile(target) as z:
    assert z.testzip() is None
    assert not any('/工作区/' in p for p in z.namelist())
print(str(target)+' | '+str(target.stat().st_size)+' bytes')
