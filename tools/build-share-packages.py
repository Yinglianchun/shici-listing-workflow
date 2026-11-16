"""Build clean application and skill archives from the current maintained files."""
import shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/01a1d4ae-2cd3-7ac0-9232-a9932a740270'
OUT.mkdir(parents=True,exist_ok=True)
date=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
def skill_files():
    base=ROOT/'skills/listing-material-workflow'
    return [(p,p.relative_to(base).as_posix()) for p in sorted(base.rglob('*'))
        if p.is_file() and p.suffix in ('.md','.yaml','.yml','.xlsx') and '__pycache__' not in p.parts]
app=[]
for p in sorted(ROOT.glob('*.py')):
    if not p.name.startswith('test_'):app.append((p,p.name))
for name in ['启动工作台.cmd','安装无边框组件.cmd','product-extractor.js','流程说明.md']:app.append((ROOT/name,name))
app.append((ROOT/'本地工作台使用说明.md','使用说明.md'))
for p in sorted((ROOT/'web').rglob('*')):
    if p.is_file():app.append((p,p.relative_to(ROOT).as_posix()))
for name in ['export-stage.mjs','table-style.mjs']:app.append((ROOT/'tools/xlsx'/name,'tools/xlsx/'+name))
for p,relative in skill_files():app.append((p,'skills/listing-material-workflow/'+relative))
for p in sorted((ROOT/'templates/ASIN_日期_流程模板').glob('*.xlsx')):app.append((p,'templates/流程模板/'+p.name))
packages=[('拾词_本地窗口版_'+date+'.zip','拾词',app,'拾词工作台_本地窗口版.zip'),
    ('商品拓词流程_Skill_'+date+'.zip','listing-material-workflow',skill_files(),'商品拓词流程_Skill.zip')]
for filename,prefix,files,alias in packages:
    target=OUT/filename
    with ZipFile(target,'w',ZIP_DEFLATED) as archive:
        for source,relative in files:archive.write(source,prefix+'/'+relative)
    with ZipFile(target) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError('压缩包读取失败：'+bad)
    shutil.copyfile(target,OUT/alias)
    print(f'{target} | {len(files)} files | {target.stat().st_size:,} bytes')
