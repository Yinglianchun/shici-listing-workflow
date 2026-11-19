"""Fixed keyword workbook layout, matching the user's reference without its overview."""
from collections import Counter,defaultdict
from cleaner import normalize,comparison_text
from ad_policy import matched_brand

CORE_HEADERS=['核心泛词','词池中裸词出现','归入该核心泛词的词量','旧等级(裸词)','处置建议']
TERM_HEADERS=['序号','关键词','核心泛词','属性数','属性明细','处置建议']
MERGE_HEADERS=['序号','保留词','合并掉的词序变体','合并原因']
REMOVED_HEADERS=['序号','关键词','旧等级','删除原因','备注']
TABS=['L0_核心泛词','一级词','二级词','三级词','四级及以上词']

def sheet(name,headers,rows):return {'name':name,'headers':headers,'rows':rows,'layout':'keyword_reference',
    'column_widths':[8,66,33,11,60,17] if headers==TERM_HEADERS else [36,22,28,18,32]}

def keyword_identity(text):
    return comparison_text(text)

def attribute_details(attributes):
    details=[]
    for a in attributes:
        if not isinstance(a,dict):continue
        words=a.get('evidence') or a.get('values') or []
        if isinstance(words,str):words=[words]
        details.extend(str(w) for w in words if w)
    return ' + '.join(dict.fromkeys(details))

def empty_template():
    return [sheet(TABS[0],CORE_HEADERS,[]),*[sheet(name,TERM_HEADERS,[]) for name in TABS[1:5]]]

def keyword_sheets(graded,groups,sources,app,representatives,product):
    kept=sorted([g for g in graded if g['kind']=='keyword' and app.get(g['group_id'],{}).get('status')=='eligible' and app.get(g['group_id'],{}).get('ad_status','eligible')=='eligible' and isinstance(g['assessment'].get('level'),int) and representatives.get(g['group_id'],g['group_id'])==g['group_id']],key=lambda g:(g['assessment']['level'],g['text'].casefold()))
    seen=set();unique=[]
    for g in kept:
        key=keyword_identity(g['text'])
        if key not in seen:unique.append(g);seen.add(key)
    kept=unique
    by_id={g['group_id']:g for g in groups};source_map={s['source_id']:s for s in sources}
    def old_levels(g):
        return ', '.join(dict.fromkeys(str(source_map[i]['raw'].get('Level','')) for i in g['sources'] if i in source_map and source_map[i]['raw'].get('Level') not in (None,'')))
    counts=Counter(normalize(g['assessment'].get('core_term') or '') for g in kept if g['assessment'].get('level') is not None)
    cores=list(dict.fromkeys(normalize(c) for c in [*product.get('core_candidates',[]),*counts] if c))
    cores=[c for c in cores if not matched_brand(c,product.get('excluded_brands',[]))]
    core_rows=[]
    for core in cores:
        if not core:continue
        bare=[g for g in groups if g['kind']=='keyword' and normalize(g['text'])==normalize(core)]
        core_rows.append([core,'是' if bare else '否',counts[core],', '.join(filter(None,(old_levels(g) for g in bare))),'建议否定'])
    plans=[sheet(TABS[0],CORE_HEADERS,core_rows)]
    for level,name in [(1,TABS[1]),(2,TABS[2]),(3,TABS[3]),(4,TABS[4])]:
        rows=[]
        for g in kept:
            a=g['assessment'];n=a.get('level')
            if not isinstance(n,int) or (n!=level if level<4 else n<4):continue
            rows.append([len(rows)+1,g['text'],normalize(a.get('core_term') or ''),n,attribute_details(a.get('attributes',[])),'建议否定' if n<=1 else '待人工确定'])
        plans.append(sheet(name,TERM_HEADERS,rows))
    return plans
