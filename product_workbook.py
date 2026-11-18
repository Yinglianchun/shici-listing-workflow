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
        sheet('确认表单',['确认项目','已有内容','请填写或确认','所属大块'],[
            ['本品与主推子体',(product.get('asin','')+' '+str(product.get('selected_variant',''))).strip(),'确认ASIN、主推子体及差异；只补已有资料的缺项','第一块'],
            ['CSV核心词候选',product.get('core_candidates',[]),'已给CSV先抽候选；未给则第二块前补，候选不自动定0级','第一/二块'],
            ['补充核心泛词',product.get('confirmed_core_terms',[]),'补充历史核心词清单、参考表或遗漏泛词；没有填无','第一/二块'],
            ['出单/销售词（可选）',product.get('sales_keyword_source',''),'年度报告可只给用户搜索词+订单数；确认ASIN及时间；没有填无','第二块'],
            ['标题、五点与参数',product.get('raw_details',product.get('facts','')),'补缺项；已有ASIN/链接时先由agent读取','第一块'],
            ['图片与页面外卖点',product.get('confirmed_supplements',''),'补充图片遗漏及实物已确认卖点，对应部件/子体；没有填无','第一块'],
            ['现有QA与A+',product.get('existing_qa',''),'已有内容不重填；没有填无，第三块只核对新增或变动','第一/三块'],
            ['广告范围与品牌',product.get('advertising_policy',''),'确认本次投放子体、排除品牌及特别取舍；不投与文案不可用分开','第二块'],
            ['本轮缺失属性',product.get('pending_questions',[]),'按当前块实际素材集中列缺项；只补相关部件/子体','当前块'],
            ['QA使用入口',product.get('qa_destination',''),'确认250字符QA填写位置及A+问答区域；已有入口不重问','第三块'],
            ['描述分配',product.get('description_targets',''),'确认接收描述的父体/子体及共用/专属范围','第四块'],
        ],column_widths=[24,48,62,22]),
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
