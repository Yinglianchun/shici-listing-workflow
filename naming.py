"""Human-readable project and export names; internal JSON identifiers stay stable."""
import json
import re
from pathlib import Path
from datetime import datetime,timezone,timedelta

def today():return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

def prefix(asin,date=None):
    asin=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(asin)).strip(' .').upper() or '未填ASIN'
    return f'{asin}_{date or today()}'

def project_directory(root,asin,date=None):
    stem=prefix(asin,date)+'_素材整理';number=1
    while True:
        folder=Path(root)/(stem if number==1 else stem+f'_{number:02d}')
        try:folder.mkdir();return folder
        except FileExistsError:number+=1

def named_file(folder,name):
    folder=Path(folder);config=folder/'job.json'
    if not config.exists() and folder.name=='表格' and (folder.parent/'job.json').exists():
        folder=folder.parent;config=folder/'job.json'
    cfg=json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
    p=cfg.get('export_prefix','')
    name=name if not p or name.startswith(p+'_') else p+'_'+name
    return folder/('表格' if cfg.get('excel_subdir')=='表格' and name.endswith('.xlsx') else '')/name


def plan_file(workbook):
    workbook=Path(workbook)
    if workbook.parent.name=='表格' and (workbook.parent.parent/'job.json').exists():
        return workbook.parent.parent/workbook.with_suffix('.plan.json').name
    return workbook.with_suffix('.plan.json')
