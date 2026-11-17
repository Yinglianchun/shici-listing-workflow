"""Own-product evidence, proposed page edits, and shared scenario references."""
import json
from pathlib import Path
from excel_export import export_excel
from output_plans import sheet
from product_analysis import analysis_sheets


def product_sheets(product=None,analysis=None):
    product=product or {};analysis=analysis or {}
    plans=[sheet('本品完整资料',['ASIN','标题','页面原文','用户确认补充','当前主推子体','待补信息'],
        [[product.get('asin',''),product.get('title',''),product.get('raw_details',product.get('facts',{})),product.get('confirmed_supplements',''),product.get('selected_variant',''),product.get('pending_questions',[])]] if product else [],column_widths=[16,38,60,48,24,36])]
    plans.extend(p for p in analysis_sheets(analysis) if p['name']!='待补资料')
    plans.extend([
        sheet('页面与补充口径',['字段或卖点','页面位置','页面原文','补充内容与来源','适用ASIN或子体','当前确认口径','状态'],[
            [r.get(k,'') for k in ('field','location','page_quote','supplement','variant','confirmed_value','status')]
            for r in analysis.get('page_consistency',[]) if isinstance(r,dict)]),
        sheet('五点修改建议',['位置','原文','建议文案','改动理由','本品依据','关联场景','状态'],[
            [r.get(k,'') for k in ('location','original','suggestion','reason','basis','scenarios','status')]
            for r in analysis.get('bullet_updates',[]) if isinstance(r,dict)]),
        sheet('需同步的页面字段',['字段','当前位置与内容','建议位置与内容','本品依据','ASIN或子体','关联QA','关联描述','状态'],[
            [r.get(k,'') for k in ('field','current','suggestion','basis','variant','qa_ids','description_role','status')]
            for r in analysis.get('page_updates',[]) if isinstance(r,dict)]),
        sheet('共用场景清单',['场景','本品依据','ASIN或子体','QA编号','描述角色','五点位置','状态'],[
            [r.get(k,'') for k in ('scenario','basis','variant','qa_ids','description_role','bullet_location','status')]
            for r in analysis.get('shared_scenarios',[]) if isinstance(r,dict)]),
        sheet('本次投放策略',['主推ASIN或子体','策略原文','确认排除品牌','确认补充'],
            [[product.get('selected_variant',''),product.get('advertising_policy',''),product.get('excluded_brands',[]),product.get('confirmed_supplements','')]] if product else []),
    ])
    return plans


def export_product(folder):
    folder=Path(folder)
    def read(name,default):
        p=folder/name
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    cfg=read('job.json',{})
    return export_excel(product_sheets(cfg.get('product',{}),read('product_analysis.json',{}).get('analysis',{}) ),folder/'本品资料与页面改动建议.xlsx')
