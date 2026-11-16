"""Blank templates mirror reader-facing outputs; review details stay internal."""
from keyword_layout import empty_template
from output_plans import question_grade_sheets,cleaned_question_sheets,prefix_sheets,description_sheets,qa_sheets
from product_analysis import analysis_sheets

def blank(name,headers):return {'name':name,'headers':headers,'rows':[],'template_rows':4}
def empty(plans):return [{**p,'rows':[],'template_rows':4} for p in plans]
def templates():
    final={'advertising_keywords':[],'prefix_groups':[],'description':'','description_selection':[],'description_limit':9000}
    return {
      '00_本品分析.xlsx':empty(analysis_sheets({})),
      '00_本品资料.xlsx':[blank('本品完整资料',['ASIN','标题','完整详情','待确认事项','资料来源'])],
      '01_导入与基础去重.xlsx':[blank('原始来源',['来源ID','文件','CSV位置','ASIN','类型','原文']),blank('基础去重',['原文ID','类型','完整原文','来源ID','ASIN'])],
      '02_相似素材排序分组.xlsx':[blank('排序分组',['排序','相似组','直接比较代表','原文ID','类型','完整原文','来源ID']),blank('相似候选',['左ID','右ID','左原文','右原文','语义相似度','文字重合度','左新词','右新词'])],
      '03_高重合素材去重.xlsx':[blank('去重与保留',['原文ID','完整原文','代表ID','决定','原因']),blank('关系原始建议',['左ID','右ID','左原文','右原文','关系','左独有信息','右独有信息','原因'])],
      '04_本品适用性筛选.xlsx':[blank('可用素材',['原文ID','类型','完整原文','来源ID'])],
      '关键词分级空模板.xlsx':empty(empty_template()),
      '05_问句与分级明细.xlsx':empty(question_grade_sheets([],{},{})),
      '06_独立QA选题与回答.xlsx':empty(qa_sheets({'qa':[],'original_questions':[]})),
      '07_短语清洗与本品复核.xlsx':empty(cleaned_question_sheets([],[])),
      '08_前缀整理与广告词.xlsx':empty(prefix_sheets(final)),
      '09_描述组合与导出.xlsx':empty(description_sheets(final)),
    }
