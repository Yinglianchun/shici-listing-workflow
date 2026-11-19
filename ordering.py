"""Program-only similarity ordering, followed by conservative, traceable deduplication."""
import re
from collections import defaultdict
from semantic import semantic_candidates,difference_hints
from cleaner import normalize, comparison_text

FUNCTION_WORDS=set('a an the do does did are is am was were these those this that it they them i you your my our us we their his her its for with of to in on at and have has had can could would will shall should be been being'.split())

def meaningful_words(text):
    return set(re.findall(r"[\w'-]+",normalize(text)))-FUNCTION_WORDS

def rank_groups(groups,vectors):
    candidates,_=semantic_candidates(groups,vectors)
    indexed={g['group_id']:g for g in groups}
    pairs={tuple(sorted((p['left'],p['right']))):p for p in candidates}
    words={g['group_id']:meaningful_words(g['text']) for g in groups}
    buckets=defaultdict(list)
    for g in groups:buckets[(g['kind'],g['marketplace'])].append(g)
    for bucket in buckets.values():
        for left in bucket:
            neighbors=[];a=words[left['group_id']]
            for right in bucket:
                if left is right:continue
                b=words[right['group_id']];union=a|b
                overlap=len(a&b)/len(union) if union else 0
                if overlap>=.65:neighbors.append((overlap,right['group_id']))
            for overlap,rid in sorted(neighbors,key=lambda r:(-r[0],r[1]))[:5]:
                key=tuple(sorted((left['group_id'],rid)))
                if key not in pairs:
                    l,r=(indexed[i] for i in key);lw,rw=words[key[0]],words[key[1]]
                    pairs[key]={'left':key[0],'right':key[1],'left_text':l['text'],'right_text':r['text'],
                        'score':0,'score_type':'text_overlap','token_overlap':round(overlap,6),
                        'left_only_tokens':sorted(lw-rw),'right_only_tokens':sorted(rw-lw),
                        'condition_hints':difference_hints(l['text'],r['text']),
                        'relation':'unjudged','status':'needs_review','reason':'文字重合候选；尚未判断是否重复'}
    candidates=sorted(pairs.values(),key=lambda p:(-max(p['score'],p['token_overlap']),p['left'],p['right']))
    adjacency=defaultdict(list)
    for pair in candidates:
        score=(pair['score']+pair['token_overlap'])/2
        adjacency[pair['left']].append((score,pair['right']))
        adjacency[pair['right']].append((score,pair['left']))
    remaining=set(indexed);ordered=[];clusters=[]
    while remaining:
        anchor=min(remaining,key=lambda i:(-sum(j in remaining for _,j in adjacency[i]),i))
        members=[anchor]+[j for _,j in sorted(adjacency[anchor],key=lambda r:(-r[0],r[1])) if j in remaining and j!=anchor]
        members=list(dict.fromkeys(members));remaining.difference_update(members)
        cid=f'S{len(clusters)+1:05d}'
        clusters.append({'sort_group':cid,'anchor':anchor,'members':members})
        base=len(ordered)
        ordered.extend({**indexed[i],'sort_group':cid,'sort_anchor':anchor,'sort_order':base+n+1} for n,i in enumerate(members))
    return {'groups':ordered,'candidates':candidates,'clusters':clusters}

def active_groups(groups,app):
    return [g for g in groups if app.get(g['group_id'],{}).get('status')=='eligible' or
            (g['kind']=='ai_generated_question' and app.get(g['group_id'],{}).get('status')=='pending')]

def duplicate_candidates(candidates,active):
    ids={g['group_id'] for g in active}
    return [p for p in candidates if p['left'] in ids and p['right'] in ids and
            (p['token_overlap']>=.65 or p['score']>=.88)]

def deduplicate_similar(groups,judgments,app):
    """Remove repeated expressions and directly covered questions; retain source lineage."""
    by_id={g['group_id']:g for g in groups};representatives={i:i for i in by_id};relations={}
    for j in judgments:
        a,b=j['left'],j['right']
        if a not in by_id or b not in by_id:continue
        if by_id[a]['kind']!=by_id[b]['kind'] or by_id[a]['marketplace']!=by_id[b]['marketplace']:continue
        if app[a].get('status')!=app[b].get('status'):continue
        aw,bw=meaningful_words(by_id[a]['text']),meaningful_words(by_id[b]['text'])
        same_expression = (comparison_text(by_id[a]['text']) == comparison_text(by_id[b]['text'])
                           if by_id[a]['kind']=='keyword' else aw==bw)
        if j.get('relation')=='equivalent' and not j.get('left_unique') and not j.get('right_unique') and same_expression:
            relations[a,b]=relations[b,a]='重复表达'
        elif by_id[a]['kind']=='ai_generated_question' and j.get('relation')=='partial_overlap':
            if j.get('left_covers_right') is True and not j.get('right_covers_left') and not j.get('right_unique') and bw<aw:
                relations[b,a]='保留句完整包含本句信息'
            if j.get('right_covers_left') is True and not j.get('left_covers_right') and not j.get('left_unique') and aw<bw:
                relations[a,b]='保留句完整包含本句信息'
    ordered=sorted(groups,key=lambda g:-len(meaningful_words(g['text'])))
    for g in ordered:
        identifier=g['group_id']
        for previous in ordered:
            pid=previous['group_id']
            if pid==identifier:break
            if representatives[pid]==pid and (identifier,pid) in relations:
                representatives[identifier]=pid;break
    return {'kept_ids':[i for i,r in representatives.items() if i==r],
        'representatives':representatives,'groups':groups,'judgments':judgments,
        'decisions':[{'id':i,'text':by_id[i]['text'],'representative_id':r,
            'decision':'保留' if i==r else '剔除，原文留在来源记录',
            'reason':'保留独有信息或未确认关系' if i==r else relations[i,r]} for i,r in representatives.items()]}

def restore_lineage(materials,groups,representatives,qa):
    qa_originals={q['id']:q['text'] for q in qa.get('original_questions',[])}
    used={normalize(qa_originals[i]) for q in qa.get('qa',[]) if q.get('answer_en') for i in q.get('covered_question_ids',[]) if i in qa_originals}
    for row in materials:
        roots=set(row['member_ids']);members=[g for g in groups if representatives.get(g['group_id']) in roots]
        row['member_ids']=[g['group_id'] for g in members];row['originals']=[g['text'] for g in members]
        row['sources']=list(dict.fromkeys(s for g in members for s in g['sources']))
        row['asins']=sorted({a for g in members for a in g['asins']})
        row['qa_used']=any(normalize(g['text']) in used for g in members)
