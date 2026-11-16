"""Build representative-based intent proposals while retaining all source variants."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
from cleaner import write_csv


def propose_intents(groups,judgments,own_asins=()):
    indexed={group['group_id']:group for group in groups}
    if len(indexed)!=len(groups):
        raise ValueError('文本组ID重复')
    own={asin.upper() for asin in own_asins}
    adjacency=defaultdict(set)
    edges={}
    conflicts=set()
    for judgment in judgments:
        a,b=judgment['left'],judgment['right']
        if a not in indexed or b not in indexed:
            raise ValueError('关系记录指向不存在的文本组')
        left,right=indexed[a],indexed[b]
        if left['text']!=judgment['left_text'] or right['text']!=judgment['right_text']:
            raise ValueError('关系记录与文本组原文不一致')
        if left['kind']!=right['kind'] or left['marketplace']!=right['marketplace']:
            raise ValueError('不能跨站点或类型归并')
        key=tuple(sorted((a,b)))
        if key in edges:
            raise ValueError('同一文本对包含重复关系记录')
        edges[key]=judgment
        relation=judgment.get('reviewed_relation') if judgment.get('status')=='confirmed' else judgment['relation']
        if relation=='equivalent' and (judgment.get('status')=='confirmed' or not judgment.get('review_flags')):
            adjacency[a].add(b)
            adjacency[b].add(a)
        elif relation not in ('unjudged','uncertain'):
            conflicts.add(key)
    remaining=set(indexed)
    proposals=[]
    while remaining:
        def priority(identifier):
            group=indexed[identifier]
            return (-len(adjacency[identifier]&remaining),-bool(own&set(group.get('asins',[]))),len(group['text']),identifier)
        representative=min(remaining,key=priority)
        selected=[representative]
        for member in sorted(adjacency[representative]&remaining,key=priority):
            if member==representative:
                continue
            if any(tuple(sorted((member,other))) in conflicts for other in selected):
                continue
            selected.append(member)
        remaining.difference_update(selected)
        members=[indexed[identifier] for identifier in selected]
        asins=sorted({asin for member in members for asin in member.get('asins',[])})
        topics=Counter()
        evidence=[]
        for member in selected[1:]:
            edge=edges[tuple(sorted((representative,member)))]
            topics.update(edge.get('topics',[]))
            evidence.append({'left':edge['left'],'right':edge['right'],
                'relation':edge.get('reviewed_relation') if edge.get('status')=='confirmed' else edge['relation'],
                'status':edge['status'],'reason':edge.get('reason','')})
        proposals.append({'proposal_id':f'I{len(proposals)+1:05}',
            'kind':members[0]['kind'],'marketplace':members[0]['marketplace'],
            'representative_id':representative,'representative_question_or_term':indexed[representative]['text'],
            'member_count':len(members),'source_record_count':sum(len(member.get('sources',[])) for member in members),
            'asins':asins,'asin_count':len(asins),'suggested_topics':[topic for topic,_ in topics.most_common()],
            'members':members,'representative_relations':evidence,
            'status':'proposed' if len(members)>1 else 'standalone',
            'meaning':'语言归并建议，来源商品的事实与回答不合并；所有原始表达均保留。'})
    return proposals


def export_intents(proposals,folder,summary):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'intent_proposals.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for kind,name in [('ai_generated_question','问句意图归并建议'),('keyword','关键词同义建议'),('unknown','未知类型')]:
        rows=[]
        for proposal in proposals:
            if proposal['kind']!=kind:
                continue
            rows.append([proposal['proposal_id'],proposal['representative_question_or_term'],
                ' | '.join(proposal['suggested_topics']),proposal['member_count'],proposal['source_record_count'],
                proposal['asin_count'],','.join(proposal['asins']),
                '\n'.join(member['text'] for member in proposal['members']),
                ','.join(source for member in proposal['members'] for source in member.get('sources',[])),proposal['status']])
        write_csv(folder/f'{name}.csv',['建议组','代表原问/原词','参考主题','独立文本组数','来源记录数','ASIN数','ASIN','全部原文表达','来源ID','状态'],rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups',type=Path,required=True)
    parser.add_argument('--judgments',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--own',default='')
    args=parser.parse_args()
    groups=json.loads(args.groups.read_text(encoding='utf-8'))
    judgments=json.loads(args.judgments.read_text(encoding='utf-8'))
    proposals=propose_intents(groups,judgments,args.own.split(','))
    candidate_file=args.groups.parent/'similar_candidates.json'
    candidate_count=len(json.loads(candidate_file.read_text(encoding='utf-8'))) if candidate_file.exists() else None
    summary={'input_text_groups':len(groups),'intent_proposals':len(proposals),
        'relationship_pairs_available':len(judgments),'candidate_pairs':candidate_count,
        'relationship_processing_complete':len(judgments)==candidate_count if candidate_count is not None else None,
        'assigned_text_groups':sum(p['member_count'] for p in proposals),
        'source_records':sum(p['source_record_count'] for p in proposals),
        'by_kind':dict(Counter(p['kind'] for p in proposals)),
        'scope':'仅代表文本的直接同义关系建议；全部原文和来源保留。未进行商品适用性筛选、分级或答案生成。'}
    export_intents(proposals,args.out,summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
