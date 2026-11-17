"""Build separate keyword/question/phrase exports and a natural-length description draft."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from cleaner import normalize,phrase,write_csv
from intents import propose_intents


def assemble(candidates,limit=9000):
    """Add intact material only while it contributes new wording; never pad or truncate."""
    selected=[];seen=set();seen_pairs=set();length=0
    for candidate in sorted(candidates,key=lambda c:(c['priority'],c.get('level') if isinstance(c.get('level'),int) else 99,len(c['text']))):
        text=re.sub(r'\s+',' ',candidate['text']).strip()
        comparison=phrase(text)['text'] if candidate.get('format')=='完整问句' else text
        tokens=re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*",normalize(comparison))
        tokens=[t for t in tokens if t not in {'good','suitable','provide','provides','available','come','comes'}]
        words=set(tokens)
        pairs=set(zip(tokens,tokens[1:]))
        new=words-seen
        if not text or (not new and not (pairs-seen_pairs)):
            continue
        cost=len(text)+(2 if selected else 0)
        if length+cost>limit:
            continue
        selected.append({**candidate,'text':text,'new_words':sorted(new)})
        seen.update(words);seen_pairs.update(pairs);length+=cost
    return '; '.join(c['text'] for c in selected),selected


def assemble_groups(candidates,limit=9000):
    """Pack intact approved phrases into as many groups as needed."""
    if limit<1:raise ValueError('每组字符上限必须大于0')
    unique={};pending=[]
    for candidate in candidates:
        text=re.sub(r'\s+',' ',candidate['text']).strip()
        if not text:continue
        key=normalize(text)
        if key in unique:
            previous=unique[key]
            previous['material_ids']=list(dict.fromkeys(previous.get('material_ids',[])+candidate.get('material_ids',[])))
            previous['priority']=min(previous['priority'],candidate['priority'])
        else:unique[key]={**candidate,'text':text}
    groups=[]
    for row in sorted(unique.values(),key=lambda c:(c['priority'],c.get('level',99),len(c['text']))):
        if len(row['text'])>limit:
            pending.append({**row,'reason':'单条超过每组上限，需重新整理；未截断'})
            continue
        if not groups or len(groups[-1]['description'])+2+len(row['text'])>limit:
            groups.append({'group_id':len(groups)+1,'description':'','selection':[],
                'target_asin':'','target_type':'','applicability':'','assignment_status':'待分配'})
        group=groups[-1]
        group['description']+=('; ' if group['selection'] else '')+row['text']
        group['selection'].append({**row,'group_id':group['group_id']})
        group['characters']=len(group['description'])
    return groups,pending


def build(groups,assessments,applicability,judgments,qa,own_asin,limit,compose=True):
    by_id={g['group_id']:g for g in groups}
    eligible=[g for g in groups if applicability.get(g['group_id'],{}).get('status')=='eligible']
    ids={g['group_id'] for g in eligible}
    relevant=[j for j in judgments if j['left'] in ids and j['right'] in ids]
    proposals=propose_intents(eligible,relevant,[own_asin])
    # New CSVs can change sequential IDs. Match the QA's original wording, never an old ID alone.
    qa_originals={q['id']:q['text'] for q in qa.get('original_questions',[])}
    used_texts={normalize(qa_originals[i]) for q in qa.get('qa',[]) if q.get('answer_en')
                for i in q.get('covered_question_ids',[]) if i in qa_originals}
    used={g['group_id'] for g in groups if g['kind']=='ai_generated_question' and normalize(g['text']) in used_texts}
    rows=[];candidates=[]
    for proposal in proposals:
        representative=proposal['representative_id'];group=by_id[representative]
        a=assessments.get(representative,{})
        level=a.get('level')
        member_ids=[g['group_id'] for g in proposal['members']]
        qa_used=bool(used&set(member_ids))
        cleaned=phrase(group['text']) if group['kind']=='ai_generated_question' else None
        # Degree/quantity questions retained by cleaner are still exported, not silently cleaned.
        phrase_ready=bool(cleaned) and not re.match(r'^how\b',cleaned['text'])
        row={'material_id':proposal['proposal_id'],'kind':group['kind'],'level':level,
             'text':group['text'],'phrase':cleaned['text'] if cleaned else '',
             'phrase_status':'待改写' if cleaned and not phrase_ready else '清洗草稿' if cleaned else '',
             'qa_used':qa_used,'member_ids':member_ids,'originals':[g['text'] for g in proposal['members']],
             'sources':list(dict.fromkeys(i for g in proposal['members'] for i in g['sources'])),
             'asins':proposal['asins'],'basis':applicability[representative].get('basis','')}
        rows.append(row)
        if level is None:
            continue
        stop=set('a an the do does are is these those this it they for with of to in on and have has provide come suitable good'.split())
        words=lambda text:set(re.findall(r'[a-z0-9]+',normalize(text)))-stop
        representative_words=words(group['text'])
        for member in proposal['members']:
            # Equivalent wording with a genuinely different term can still be useful material.
            if member['group_id']!=representative and not (words(member['text'])-representative_words):
                continue
            cleaned_member=phrase(member['text']) if member['kind']=='ai_generated_question' else None
            if member['kind']=='ai_generated_question' and re.match(r'^how\b',cleaned_member['text']):
                continue
            text=member['text'] if member['kind']=='keyword' else cleaned_member['text']
            candidates.append({'material_id':row['material_id'],'group_id':member['group_id'],'text':text,'kind':group['kind'],
                'level':level,'priority':0 if qa_used else 1 if group['kind']=='keyword' else 2,
                'format':'关键词' if group['kind']=='keyword' else '清洗短语'})
    description,selected=assemble(candidates,limit) if compose else ('',[])
    selected_ids={c['material_id'] for c in selected}
    for row in rows:row['included_in_description']=row['material_id'] in selected_ids
    hold=[{**g,'applicability':applicability.get(g['group_id'],{})} for g in groups if g['group_id'] not in ids]
    return {'materials':rows,'held_materials':hold,'description':description,'description_selection':selected,
        'summary':{'input_groups':len(groups),'applicability':dict(Counter(applicability.get(g['group_id'],{}).get('status','pending') for g in groups)),
        'eligible_groups':len(eligible),'merged_materials':len(rows),'materials_by_kind':dict(Counter(r['kind'] for r in rows)),
        'description_characters':len(description),'description_limit':limit,'description_items':len(selected),
        'scope':'商品资料支持的素材草稿；模型适用性建议仍需核对。字符数是上限，不补齐、不截断单条。'}}


def export(result,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'materials.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(result['summary'],ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'商品描述素材草稿.txt').write_text(result['description'],encoding='utf-8',newline='\n')
    if result.get('core_terms'):
        write_csv(out/'核心泛词.csv',['核心泛词','等级','ASIN','依据'],[[c['text'],0,c['asin'],c['basis']] for c in result['core_terms']])
    headers=['素材ID','等级','原文代表','清洗短语','QA已用','原问/原词ID','全部原文','ASIN','来源ID','资料依据','进入描述','清洗状态']
    for kind,name in [('keyword','关键词'),('ai_generated_question','完整问句')]:
        rows=[r for r in result['materials'] if r['kind']==kind]
        write_csv(out/f'{name}.csv',headers,[[r['material_id'],r['level'] if r['level'] is not None else '',r['text'],r['phrase'],r['qa_used'],','.join(r['member_ids']), '\n'.join(r['originals']),','.join(r['asins']),','.join(r['sources']),r['basis'],r['included_in_description'],r['phrase_status']] for r in rows])
    rows=[r for r in result['materials'] if r['kind']=='ai_generated_question']
    write_csv(out/'整理后的问句.csv',['素材ID','等级','清洗短语','完整原问','清洗状态','来源ID'],
        [[r['material_id'],r['level'] if r['level'] is not None else '',r['phrase'],r['text'],r['phrase_status'],','.join(r['sources'])] for r in rows])
    write_csv(out/'不适用及待补资料.csv',['文本组','类型','原文','状态','原因','缺少资料','来源ID'],
        [[g['group_id'],g['kind'],g['text'],g['applicability'].get('status','pending'),g['applicability'].get('reason',''),str(g['applicability'].get('missing_information',[])),','.join(g['sources'])] for g in result['held_materials']])
    if 'advertising_keywords' in result:
        write_csv(out/'广告关键词.csv',['关键词'],[[r['keyword']] for r in result['advertising_keywords']])
        write_csv(out/'合并前再次自查.csv',['素材ID','原文','自查建议','原因','依据'],[[r['material']['material_id'],r['material']['text'],r['review'].get('status'),r['review'].get('reason'),r['review'].get('basis')] for r in result['final_reviews']])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--grades',type=Path,nargs='+',required=True)
    parser.add_argument('--applicability',type=Path,required=True)
    parser.add_argument('--judgments',type=Path,required=True)
    parser.add_argument('--qa',type=Path,required=True)
    parser.add_argument('--own',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--max-characters',type=int,default=9000)
    args=parser.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
    groups=read(args.input/'groups.json')
    grades={g['group_id']:g['assessment'] for file in args.grades for g in read(file)}
    result=build(groups,grades,read(args.applicability),read(args.judgments),read(args.qa),args.own,args.max_characters)
    export(result,args.out)
    print(json.dumps(result['summary'],ensure_ascii=False))


if __name__=='__main__':main()
