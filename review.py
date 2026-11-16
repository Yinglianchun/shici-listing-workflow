"""Build a standalone relationship review page from judgment output."""
import argparse
import json
from pathlib import Path

RELATIONS={'equivalent','partial_overlap','same_topic','different','uncertain'}


def apply_decisions(rows,document):
    decisions=document.get('decisions') if isinstance(document,dict) else None
    if not isinstance(decisions,list):
        raise ValueError('确认文件缺少 decisions 数组')
    indexed={(row['left'],row['right']):row for row in rows}
    updates={}
    for decision in decisions:
        if not isinstance(decision,dict):
            raise ValueError('确认记录必须为对象')
        key=(decision.get('left'),decision.get('right'))
        row=indexed.get(key)
        if key in updates or not row:
            raise ValueError('确认记录的文本组不存在或重复')
        if decision.get('left_text')!=row['left_text'] or decision.get('right_text')!=row['right_text']:
            raise ValueError('确认记录的原文与当前数据不符')
        if decision.get('relation') not in RELATIONS:
            raise ValueError('确认记录包含未知关系')
        updates[key]=decision
    result=[]
    for row in rows:
        updated=dict(row)
        decision=updates.get((row['left'],row['right']))
        if decision:
            updated.update({'reviewed_relation':decision['relation'],'reviewed_at':decision.get('reviewed_at'), 'status':'confirmed'})
        result.append(updated)
    return result


def build_review(folder):
    folder=Path(folder)
    rows=json.loads((folder/'judgments.json').read_text(encoding='utf-8'))
    summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    original=Path(summary.get('input',folder))
    if (original/'groups.json').exists() and (original/'sources.json').exists():
        groups={group['group_id']:group for group in json.loads((original/'groups.json').read_text(encoding='utf-8'))}
        sources={source['source_id']:source for source in json.loads((original/'sources.json').read_text(encoding='utf-8'))}
        for row in rows:
            for side in ('left','right'):
                group=groups.get(row[side],{})
                provenance=[]
                for identifier in group.get('sources',[]):
                    source=sources[identifier]
                    raw=source['raw']
                    provenance.append({'asin':raw['ASIN'],'marketplace':raw.get('Marketplace',''),
                        'file':Path(source['file']).name,'record':source['csv_record'],'source_id':identifier,
                        'source_type':source['kind'],'imported_evidence':raw.get('Evidence','')})
                row[f'{side}_provenance']=provenance
    payload={'source':str(folder.resolve()),'summary':summary,'rows':rows}
    template=(Path(__file__).parent/'templates'/'review.html').read_text(encoding='utf-8')
    # Page text is untrusted input, including any closing script tags.
    data=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')
    output=folder/'review.html'
    output.write_text(template.replace('__REVIEW_DATA__',data),encoding='utf-8')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--decisions',type=Path,help='将导出的人工确认记录应用到一份新结果')
    parser.add_argument('--out',type=Path,help='应用确认记录时的新输出目录')
    args=parser.parse_args()
    folder=args.input
    if args.decisions:
        if not args.out:
            parser.error('--decisions 需要 --out 指定新目录')
        rows=json.loads((args.input/'judgments.json').read_text(encoding='utf-8'))
        document=json.loads(args.decisions.read_text(encoding='utf-8'))
        updated=apply_decisions(rows,document)
        summary=json.loads((args.input/'summary.json').read_text(encoding='utf-8'))
        summary['confirmed_pairs']=sum(row['status']=='confirmed' for row in updated)
        args.out.mkdir(parents=True,exist_ok=False)
        (args.out/'judgments.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8')
        (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        folder=args.out
    print(build_review(folder).resolve())
