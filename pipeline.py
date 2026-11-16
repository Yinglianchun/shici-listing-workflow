"""Finish imported material: applicability, separate QA branch, merge, clean, compose, export."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from applicability import assess
from materials import build,export
from grading import prepare_items,analyse,compute_level
from judge import DEFAULT_MODEL
from finalize import final_comparison,compose_reviewed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,help='CSV导入和基础去重结果目录')
    parser.add_argument('--csv',type=Path,nargs='+',help='直接传入任意数量的CSV或CSV目录')
    parser.add_argument('--product',type=Path,required=True)
    parser.add_argument('--grades',type=Path,nargs='*',default=[])
    parser.add_argument('--judgments',type=Path)
    parser.add_argument('--qa',type=Path,help='独立原问选题结果，不从合并结果选QA')
    parser.add_argument('--applicability',type=Path,help='直接复用已有适用性结果，不请求模型')
    parser.add_argument('--decisions',type=Path,help='人工适用性修正，按类型和原文匹配，不改原模型记录')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--max-characters',type=int,default=9000)
    parser.add_argument('--xlsx',action='store_true')
    parser.add_argument('--llm-model',default=DEFAULT_MODEL)
    parser.add_argument('--embedding-model',default='BAAI/bge-m3')
    args=parser.parse_args()
    if not args.input and not args.csv:parser.error('请提供 --input 或 --csv')
    from workbench_worker import run,STAGES,save
    from datetime import datetime
    args.out.mkdir(parents=True,exist_ok=True)
    inputs=[]
    for path in args.csv or []:
        inputs.extend(str(p.resolve()) for p in (sorted(path.glob('*.csv')) if path.is_dir() else [path]))
    cfg={'workflow':'dedup-first','created':datetime.now().strftime('%Y-%m-%d %H:%M'),
        'inputs':inputs,'product':json.loads(args.product.read_text(encoding='utf-8')),
        'llm_model':args.llm_model,'embedding_model':args.embedding_model,'max_characters':args.max_characters,
        'reuse_grades':[str(p.resolve()) for p in args.grades]}
    for flag,target in [('input','import_folder'),('judgments','reuse_judgments'),('qa','reuse_qa'),('applicability','reuse_applicability'),('decisions','decisions')]:
        value=getattr(args,flag)
        if value:cfg[target]=str(value.resolve())
    job=args.out/'job.json'
    if job.exists():
        previous=json.loads(job.read_text(encoding='utf-8'))
        cfg['workflow']=previous.get('workflow',cfg['workflow'])
        cfg['created']=previous.get('created',cfg['created'])
        for field in ['id','export_prefix']:
            if field in previous:cfg[field]=previous[field]
        if previous!=cfg:raise ValueError('此输出目录已有另一份任务配置，请指定新的输出目录以保留已有结果。')
    else:
        import uuid
        from naming import prefix
        cfg['id']=uuid.uuid4().hex;cfg['export_prefix']=prefix(cfg['product']['asin'])
        save(job,cfg);save(args.out/'status.json',{'state':'pending','steps':[{'name':name,'state':'pending'} for name in STAGES]})
    run(args.out,9)
    print((args.out/'status.json').read_text(encoding='utf-8'))

if __name__=='__main__':main()
