"""Second product comparison, shared-prefix compaction and separate advertising keywords."""
import re
from cleaner import normalize
from applicability import assess
from materials import assemble
from keyword_layout import keyword_identity


def negative_candidates(groups,app,graded,roots):
    assessments={g['group_id']:g['assessment'] for g in graded};output={}
    def add(text,kind,level,reason,basis,sources):
        key=(kind,normalize(text))
        if key in output:
            output[key]['sources']=list(dict.fromkeys(output[key]['sources']+sources))
        else:output[key]={'text':text,'kind':kind,'level':level,'reason':reason,'basis':basis,'sources':list(sources)}
    for g in groups:
        identifier=g['group_id']
        if roots.get(identifier,identifier)!=identifier:continue
        decision=app.get(identifier,{});a=assessments.get(identifier,{});level=a.get('level')
        if decision.get('status')=='eligible' and isinstance(level,int):
            if level<=1:add(g['text'],g['kind'],level,f'{level}级：按用户规则建议否定',decision.get('basis',''),g['sources'])
            if g['kind']=='keyword' and a.get('core_term'):
                add(normalize(a['core_term']),'keyword',0,'0级核心泛词：按用户规则建议否定',decision.get('basis',''),g['sources'])
        elif decision.get('status')=='exclude' and g['kind']=='keyword':
            add(g['text'],g['kind'],level,'明确不符：'+decision.get('reason','本品不适用'),decision.get('basis',''),g['sources'])
    return sorted(output.values(),key=lambda r:(r['level'] if isinstance(r['level'],int) else 99,r['kind'],normalize(r['text'])))


def prefix_groups(items,min_words=3,ratio=.6):
    remaining=list(items);output=[]
    while remaining:
        candidates={}
        for index,item in enumerate(remaining):
            words=item['text'].split()
            for count in range(min_words,len(words)):
                key=tuple(w.casefold() for w in words[:count])
                if count/len(words)>=ratio:candidates.setdefault(key,[]).append(index)
        choices=[(len(key)*(len(set(ids))-1),len(key),key,sorted(set(ids))) for key,ids in candidates.items() if len(set(ids))>1]
        if not choices:
            output.extend({'text':i['text'],'prefix':'','suffixes':[],'members':[i]} for i in remaining)
            break
        _,count,_,indices=max(choices)
        members=[remaining[i] for i in indices]
        prefix=' '.join(members[0]['text'].split()[:count])
        suffixes=list(dict.fromkeys(' '.join(m['text'].split()[count:]) for m in members))
        text=prefix+' ('+'; '.join(suffixes)+')'
        # Only compact when it actually saves space; originals stay in members.
        if len(text)>=sum(len(m['text']) for m in members):
            first=remaining.pop(0);output.append({'text':first['text'],'prefix':'','suffixes':[],'members':[first]})
        else:
            output.append({'text':text,'prefix':prefix,'suffixes':suffixes,'members':members})
            remaining=[i for index,i in enumerate(remaining) if index not in indices]
    return output


def final_comparison(materials,product,cache,model):
    inputs=[{'group_id':r['material_id'],'kind':r['kind'],
        'text':'原文：'+' | '.join(r['originals'])+'\n清洗后：'+r['phrase']} for r in materials]
    decisions,stats=assess(inputs,product,cache,model=model,final=True)
    return [{'material':r,'review':decisions.get(r['material_id'],{'status':'pending','reason':'未取得本条自查结果'})} for r in materials],stats


def compose_reviewed(reviews,limit=9000):
    passed=[r['material'] for r in reviews if r['review'].get('status')=='eligible' and r['material'].get('level') is not None]
    keywords=[];seen=set();description_items=[]
    for row in sorted(passed,key=lambda r:(r['level'],r['text'].casefold())):
        if row['kind']=='keyword':
            term=normalize(row['text'])
            identity=keyword_identity(term)
            if identity not in seen:
                keywords.append({'keyword':term,'level':row['level'],'sources':row['sources'],'material_id':row['material_id']});seen.add(identity)
        text=row['text'] if row['kind']=='keyword' else row['phrase']
        if not text or (row['kind']=='ai_generated_question' and re.match(r'^how\b',text)):continue
        description_items.append({'text':text,'material_id':row['material_id'],'level':row['level'],
            'priority':0 if row['qa_used'] else 1 if row['kind']=='keyword' else 2,
            'format':'关键词' if row['kind']=='keyword' else '清洗短语'})
    # QA usage affects priority, never whether a question bypasses phrase cleaning.
    compact=[]
    for format in ['关键词','清洗短语']:
        compact.extend(prefix_groups([r for r in description_items if r['format']==format]))
    candidates=[{'text':g['text'],'priority':min(m['priority'] for m in g['members']),
        'level':min(m['level'] for m in g['members']),'format':g['members'][0]['format'],
        'material_ids':[m['material_id'] for m in g['members']]} for g in compact]
    text,selection=assemble(candidates,limit)
    return {'advertising_keywords':keywords,'prefix_groups':compact,'description':text,'description_selection':selection,
        'reviewed_count':len(reviews),'passed_count':len(passed),'description_characters':len(text),'description_limit':limit}
