"""Reader-facing outputs contain usable material; review details stay in stage JSON."""
import re
from cleaner import normalize
from keyword_layout import attribute_details

def sheet(name,headers,rows,**options):return {'name':name,'headers':headers,'rows':rows,**options}
def level_key(row):return (row.get('level',99),row.get('text','').casefold())
def bucket(level):return min(level,4)

def screened_sheets(groups,app):
    good=sorted([g for g in groups if app.get(g['group_id'],{}).get('status')=='eligible'],key=lambda g:(g['kind'],g['text'].casefold()))
    return [sheet('可用素材',['原文ID','类型','完整原文','来源ID'],[[g['group_id'],g['kind'],g['text'],g['sources']] for g in good])]

def question_grade_sheets(graded,app,roots):
    good=sorted([g for g in graded if g['kind']=='ai_generated_question' and app.get(g['group_id'],{}).get('status')=='eligible'
        and roots.get(g['group_id'],g['group_id'])==g['group_id'] and isinstance(g['assessment'].get('level'),int)],
        key=lambda g:(g['assessment']['level'],g['text'].casefold()))
    plans=[]
    for level,name in enumerate(['L0_原问','一级问句','二级问句','三级问句','四级及以上问句']):
        rows=[];seen=set()
        for g in good:
            a=g['assessment'];text=normalize(g['text'])
            if bucket(a['level'])!=level or text in seen:continue
            seen.add(text);rows.append([len(rows)+1,g['text'],a.get('core_term',''),a['level'],attribute_details(a.get('attributes',[])),a.get('topic',''),'建议否定' if a['level']<=1 else '待人工确定'])
        plans.append(sheet(name,['序号','完整问句','核心泛词','属性数','属性明细','方向','处置建议'],rows))
    return plans

def approved_ids(reviews):
    return {i for r in reviews if r['review'].get('status')=='eligible' for i in r['material']['member_ids']}

def cleaned_question_sheets(reviews,graded):
    assessments={g['group_id']:g['assessment'] for g in graded}
    good=sorted([r['material'] for r in reviews if r['review'].get('status')=='eligible'
        and r['material']['kind']=='ai_generated_question' and isinstance(r['material'].get('level'),int)],key=level_key)
    plans=[]
    for level,name in enumerate(['L0_整理后问句','一级问句','二级问句','三级问句','四级及以上问句']):
        rows=[];seen=set()
        for m in good:
            text=normalize(m['phrase'])
            if bucket(m['level'])!=level or not text or re.match(r'^how\b',text) or text in seen:continue
            seen.add(text);a=next((assessments[i] for i in m['member_ids'] if i in assessments),{})
            rows.append([len(rows)+1,m['phrase'],m['text'],a.get('core_term',''),m['level'],attribute_details(a.get('attributes',[])),a.get('topic',''),'建议否定' if m['level']<=1 else '待人工确定'])
        plans.append(sheet(name,['序号','整理后问句','完整原问','核心泛词','属性数','属性明细','方向','处置建议'],rows))
    return plans

def prefix_sheets(final):
    plans=[sheet('完整广告关键词',['关键词','等级','来源ID','处置建议'],[[r['keyword'],r['level'],r['sources'],'建议否定' if r['level']<=1 else '待人工确定'] for r in sorted(final['advertising_keywords'],key=lambda r:(r['level'],r['keyword']))])]
    plans.append(sheet('否定关键词候选',['完整词句','类型','等级','建议原因','本品依据','来源ID','匹配方式'],[
        [r['text'],r['kind'],r.get('level'),r['reason'],r.get('basis',''),r['sources'],'待选择'] for r in final.get('negative_keyword_candidates',[])]))
    for format,name in [('关键词','关键词前缀素材'),('清洗短语','问句短语前缀素材')]:
        groups=[g for g in final['prefix_groups'] if g['members'][0]['format']==format]
        groups.sort(key=lambda g:(min(m['level'] for m in g['members']),g['text']))
        plans.append(sheet(name,['等级','整理文本','共同前缀','不同后缀','完整原句'],[[min(m['level'] for m in g['members']),g['text'],g['prefix'],g['suffixes'],[m['text'] for m in g['members']]] for g in groups]))
    return plans

def description_sheets(final):
    return [sheet('描述草稿',['描述素材','实际字符数','字符上限'],[[final['description'],len(final['description']),final['description_limit']]],layout='description'),
        sheet('采用明细',['等级','文本','格式','素材ID'],[[r['level'],r['text'],r['format'],r.get('material_ids',[])] for r in sorted(final['description_selection'],key=level_key)])]

def qa_sheets(qa):
    questions=qa['qa']
    return [sheet('QA选题与回答',['编号','方向','英文问题','中文问题','QA英文回答','字符数','中文译文','本品依据','待补资料'],
        [[q.get('qa_id'),q.get('topic'),q.get('question_en',''),q.get('question_zh',''),q.get('answer_en',''),len(q.get('answer_en','')),q.get('answer_zh',''),q.get('basis',''),q.get('pending_questions',[])] for q in questions]),
        sheet('A+回答',['编号','英文问题','A+副标题','A+英文回答','字符数','A+中文译文','本品依据'],
        [[q.get('qa_id'),q.get('question_en',''),q.get('aplus_subtitle_en',''),q.get('aplus_answer_en',''),len(q.get('aplus_answer_en','')),q.get('aplus_answer_zh',''),q.get('basis','')] for q in questions]),
        sheet('原问关联',['编号','方向','实际覆盖原问ID','候选原问ID'],[[q.get('qa_id'),q.get('topic'),q.get('covered_question_ids',[]),q.get('candidate_question_ids',[])] for q in questions]),
        sheet('完整原问池',['原问ID','完整原问','来源ASIN'],[[q['id'],q['text'],q.get('asins',[])] for q in qa.get('original_questions',[])])]
