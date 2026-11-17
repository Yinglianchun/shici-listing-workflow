"""One progressively filled workbook, using the supplied reference's column layout."""
import json
from collections import Counter
from pathlib import Path
from cleaner import normalize
from excel_export import export_excel
from keyword_layout import attribute_details
from naming import named_file
from product_analysis import analysis_sheets
from finalize import merge_product_reviews

KW_HEADERS=['Keyword','属性数','核心词','Modifiers','Intent','Level(源表)','出现ASIN数','涉及ASIN','Evidence','建议']
Q_HEADERS=['Keyword','长度','原问句','处理','属性数','核心词','Modifiers','Intent','Level(源表)','出现ASIN数','涉及ASIN','Evidence','建议']
GRADE_NAMES=['0-1级','2级','3级','4级及以上']


def read(folder,name,default):
    path=Path(folder)/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def sheet(name,headers,rows=None,note='',header_row=4,widths=None):
    return {'name':name,'headers':headers,'rows':rows or [],'header_row':header_row,'layout':'master_reference',
            'title':name,'note':note,'column_widths':widths or [40 if h in ('Keyword','原问句','Evidence','内容','说明','完整词句') else 28 if h in ('Modifiers','Intent','原因','依据') else 16 for h in headers]}


def blank_master_sheets(product_sections=True):
    plans=[sheet('统计摘要',['项目','关键词','问句','说明'],note='各阶段回填同一份总表；来源次数不是搜索量或真实买家频次。',widths=[30,16,16,64])]
    for name in GRADE_NAMES:
        for kind,headers in [('关键词',KW_HEADERS),('问句',Q_HEADERS)]:
            note='精准否定候选；不用于正向投放。' if name=='0-1级' else '正向投放候选；仅采用本品资料支持的素材。'
            if kind=='问句':note+=' A列填清洗后文本，C列完整原问不改；清洗前A列留空。'
            plans.append(sheet(name+'-'+kind,headers,note=note))
    plans.insert(3,sheet('词组否定',['Keyword','否词类型','受挡搜索意图','为什么否','状态'],header_row=2,note=''))
    plans.extend([
        sheet('本品资料',['ASIN','标题','商品详情','用户待确认'],widths=[16,40,60,36]),
        sheet('子体备用',['Keyword','类型','适用子体','原因','本品依据','来源ASIN'],note='仅记录已确认子体支持的素材，不把偏光词统一当备用。'),
        sheet('已剔除-附原因',['Keyword','类型','不相关原因','属性数','核心词','Modifiers','Intent','Level(源表)','涉及ASIN'],note='保留完整原文及排除理由；不据此自动否定宽泛单词。'),
        sheet('待确认素材',['Keyword','类型','待确认原因','缺失资料','来源ASIN'],note='未作为已确认广告/描述素材；原问仍可参与QA选题。'),
        sheet('否定方向建议',['候选词组','受挡搜索意图','判断','原因'],note='从本品分析提出，不能把其他商品的small、polarized等否定词直接照搬。'),
        sheet('其他否定候选',['完整词句','类型','等级','原因','依据','来源ID','匹配方式']),
    ])
    for p in analysis_sheets({}):plans.append(sheet(p['name'],p['headers'],widths=p.get('column_widths')))
    if not product_sections:
        plans=[p for p in plans if p['name'] not in {'本品资料','本品分析','资料差异','待补资料'}]
        plans[0]['note']='按当前子体及已确认投放策略维护；本次不投不等于本品没有该特性，原文保留。'
        plans.append(sheet('04b_本次投放排除',['Keyword','类型','本品事实判断','投放处理','原因','适用子体','文案处理','来源ASIN'],note='本次不投不等于本品没有该特性；可按已确认子体和策略恢复。'))
    return plans


def build_master(folder,stage=0):
    folder=Path(folder);cfg=read(folder,'job.json',{});product=cfg.get('product',{})
    imported=read(folder,'stage1.json',{});sources=imported.get('sources',[]);groups=imported.get('groups',[])
    indexed={g['group_id']:g for g in groups};source_map={s['source_id']:s for s in sources}
    dedup=read(folder,'stage3.json',{});roots=dedup.get('representatives',{});kept=set(dedup.get('kept_ids',indexed))
    app=read(folder,'stage4.json',{});graded=read(folder,'stage5.json',[])
    changes=read(folder,'review_decisions.json',{})
    reviews=read(folder,'stage7.json',[])
    if cfg.get('report_mode')=='four-workbooks':app=merge_product_reviews(app,reviews,changes)
    else:
        for entry in reviews:
            review={**entry['review'],**changes.get(entry['material']['material_id'],{})}
            for identifier in entry['material']['member_ids']:app[identifier]={**app.get(identifier,{}),**review}
    assessments={g['group_id']:g.get('assessment',{}) for g in graded}
    suite=cfg.get('report_mode')=='four-workbooks'
    plans=blank_master_sheets(not suite);tabs={p['name']:p for p in plans}
    if not suite:tabs['本品资料']['rows']=[[product.get('asin',''),product.get('title',''),product.get('raw_details',product.get('facts',{})),product.get('pending_questions',[])]]
    analysis=read(folder,'product_analysis.json',{}).get('analysis',{})
    if not suite:
        for p in analysis_sheets(analysis):tabs[p['name']]['rows']=p['rows']
    qa=read(folder,'stage6.json',{'qa':[],'original_questions':[]})
    directions=analysis.get('negative_directions',[])
    for r in directions:
        if not isinstance(r,dict):continue
        status=r.get('status','pending')
        tabs['否定方向建议']['rows'].append([r.get('phrase',''),r.get('blocked_intent',''),{'recommended':'建议','pending':'待确认','not_recommended':'不建议'}.get(status,status),r.get('reason','')])
        if status=='recommended':tabs['词组否定']['rows'].append([r.get('phrase',''),'词组否定',r.get('blocked_intent',''),r.get('reason',''),'建议'])
    fixed=cfg.get('fixed_negative_phrases',[])
    for phrase in fixed:
        if not phrase.strip():continue
        tabs['词组否定']['rows']=[r for r in tabs['词组否定']['rows'] if normalize(r[0])!=normalize(phrase)]
        tabs['词组否定']['rows'].append([phrase,'词组否定','用户指定','用户确认固定加入','已确认'])
    def metadata(g,a):
        old=list(dict.fromkeys(str(source_map[s]['raw'].get('Level','')) for s in g.get('sources',[]) if s in source_map))
        basis=list(dict.fromkeys(str(source_map[s]['raw'].get('Evidence','')) for s in g.get('sources',[]) if s in source_map))
        return [a.get('level'),a.get('core_term',''),attribute_details(a.get('attributes',[])),a.get('intent',''),', '.join(filter(None,old)),len(g.get('asins',[])),g.get('asins',[]),'；'.join(filter(None,basis))]
    # The refreshed stage plans define which graded rows survived final product review.
    keyword_plans=read(folder,'stage5.plan.json',[])
    approved_kw={normalize(r[1]) for p in keyword_plans if p.get('name')!='L0_核心泛词' for r in p.get('rows',[]) if len(r)>1}
    question_plans=read(folder,'stage5_questions.plan.json',[])
    approved_q={normalize(r[1]) for p in question_plans for r in p.get('rows',[]) if len(r)>1}
    cleaned={normalize(r[2]):r[1] for p in read(folder,'stage7.plan.json',[]) for r in p.get('rows',[]) if len(r)>2}
    clean_done=(folder/'stage7.json').exists()
    for g in graded:
        identifier=g['group_id'];a=g.get('assessment',{});level=a.get('level')
        decision=app.get(identifier,{})
        if identifier not in kept or decision.get('status')!='eligible' or decision.get('ad_status','eligible')!='eligible' or not isinstance(level,int):continue
        is_keyword=g['kind']=='keyword';text=normalize(g['text'])
        if is_keyword and keyword_plans and level>0 and text not in approved_kw:continue
        if not is_keyword and question_plans and text not in approved_q:continue
        if not is_keyword and clean_done and text not in cleaned:continue
        name=GRADE_NAMES[0 if level<=1 else 1 if level==2 else 2 if level==3 else 3]+('-关键词' if is_keyword else '-问句')
        advice='精准否定' if level<=1 else '正向候选'
        if is_keyword:row=[g['text'],*metadata(g,a),advice]
        else:
            phrase=cleaned.get(text,'')
            row=[phrase,len(phrase),g['text'],'已清洗，原问保留' if phrase else '待07清洗',*metadata(g,a),advice]
        tabs[name]['rows'].append(row)
    # Include actual derived core terms, never the reference product's hard-coded list.
    existing={normalize(r[0]) for r in tabs['0-1级-关键词']['rows']}
    for p in keyword_plans:
        if p.get('name')!='L0_核心泛词':continue
        for r in p.get('rows',[]):
            if r and normalize(r[0]) not in existing:
                tabs['0-1级-关键词']['rows'].append([r[0],0,r[0],'','核心泛词','',0,[],'由本次核心词归纳','精准否定']);existing.add(normalize(r[0]))
    for g in groups:
        identifier=g['group_id'];decision=app.get(identifier,{});status=decision.get('status')
        if identifier not in kept:continue
        if suite and decision.get('ad_status') in ('exclude','pending'):
            tabs['04b_本次投放排除']['rows'].append([g['text'],g['kind'],status,decision['ad_status'],decision.get('ad_reason',''),decision.get('variant',product.get('selected_variant','')),decision.get('copy_status',status),g.get('asins',[])])
        if status=='exclude':
            a=assessments.get(identifier,{})
            m=metadata(g,a)
            tabs['已剔除-附原因']['rows'].append([g['text'],g['kind'],decision.get('reason',''),m[0],m[1],m[2],m[3],m[4],g.get('asins',[])])
        elif status=='pending':tabs['待确认素材']['rows'].append([g['text'],g['kind'],decision.get('reason',''),decision.get('missing_information',[]),g.get('asins',[])])
        elif status=='variant_only':tabs['子体备用']['rows'].append([g['text'],g['kind'],decision.get('variant',''),decision.get('reason',''),decision.get('basis',''),g.get('asins',[])])
    final=read(folder,'stage9.json',read(folder,'stage8.json',{}))
    for r in final.get('negative_keyword_candidates',[]):
        if r.get('level') in (0,1):continue
        tabs['其他否定候选']['rows'].append([r['text'],r['kind'],r.get('level'),r.get('reason',''),r.get('basis',''),r.get('sources',[]),'待选择'])
    source_counts=Counter(s.get('kind') or {'关键词':'keyword','买家问句':'ai_generated_question'}.get(s.get('raw',{}).get('Type'),s.get('raw',{}).get('Type','unknown')) for s in sources)
    pending=sum(app.get(i,{}).get('status')=='pending' for i in kept)
    deleted_pending=sum(i not in kept and r.get('status')=='pending' for i,r in app.items())
    stats=[['ASIN','','',product.get('asin','')],['商品','','',product.get('title','')],
           ['原始素材',source_counts['keyword'],source_counts['ai_generated_question'],'AI生成素材，不是真实买家提问或搜索量'],
           ['基础去重后',sum(g['kind']=='keyword' for g in groups),sum(g['kind']=='ai_generated_question' for g in groups),'保留来源'],
           ['待确认代表','','',pending],['删除留档的待确认原文','','',deleted_pending]]
    for name in GRADE_NAMES:stats.append([name,len(tabs[name+'-关键词']['rows']),len(tabs[name+'-问句']['rows']),'精准否定候选' if name=='0-1级' else '正向候选'])
    for i,s in enumerate(read(folder,'status.json',{}).get('steps',[]),1):stats.append([f'{i:02d} '+s.get('name',''),'','', '已完成' if i==stage or s.get('state')=='done' else s.get('state','pending')])
    stats.extend([['QA','','',len(qa.get('qa',[]))],['描述字符数','','',final.get('description_total_characters',len(final.get('description','')))],['每组字符上限' if suite else '字符上限','','',cfg.get('max_characters',9000)]])
    if suite:stats.append(['描述组数','','',len(final.get('description_groups',[]))])
    tabs['统计摘要']['rows']=stats
    tabs['统计摘要']['title']=cfg.get('export_prefix',product.get('asin','ASIN'))+(' · 投放分级关键词与问句' if suite else ' · 素材总表')
    for name in GRADE_NAMES:
        for kind in ('关键词','问句'):
            rows=tabs[name+'-'+kind]['rows'];level_col=1 if kind=='关键词' else 4
            rows.sort(key=lambda r:(r[level_col],normalize(str(r[0] or r[2]))))
    return plans


def update_master(folder,stage,plans=None):
    folder=Path(folder)
    if plans is not None:(folder/f'stage{stage}.plan.json').write_text(json.dumps(plans,ensure_ascii=False),encoding='utf-8')
    cfg=read(folder,'job.json',{})
    name='投放分级关键词与问句.xlsx' if cfg.get('report_mode')=='four-workbooks' else '素材总表.xlsx'
    return export_excel(build_master(folder,stage),folder/name)
