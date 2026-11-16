"""Compact reader-facing column names and widths, shared by every stage export."""
import unicodedata
HEADER_NAMES={
    '完整详情':'商品详情','待确认事项':'待确认','资料来源':'来源','CSV位置':'行号','完整原文':'原文',
    '直接比较代表':'比较ID','语义相似度':'语义分','文字重合度':'文字分','左独有信息':'左侧差异','右独有信息':'右侧差异',
    '独立属性':'属性明细','属性原文依据':'属性依据','本品适用性':'适用性','复核建议':'复核结果','自查建议':'复核结果',
    '英文问题':'问题','中文问题':'问题中译','QA英文回答':'QA回答','中文译文':'回答中译','A+英文回答':'A+回答',
    'A+中文译文':'A+中译','实际覆盖原问ID':'覆盖ID','候选原问ID':'候选ID','选择理由':'选题理由',
    '完整原问':'原问','完整问句':'问句','来源ASIN':'ASIN','选题状态':'选题结果','清洗后':'清洗短语',
    '合并前全部原文':'原文变体','全部原文':'原文变体','整理后文本':'整理文本','完整原句':'原句',
    '描述素材':'描述稿','实际字符数':'字符数','字符上限':'上限','模型原建议':'模型建议','原模型建议':'模型建议',
    '采用建议':'采用结果','人工修改':'人工调整',
}

def compact_header(header):return HEADER_NAMES.get(header,header)

def column_width(header):
    """A readable width, not the full length of a 500-character answer."""
    name=compact_header(header)
    if name in ('序号','等级','属性数','字符数','上限','行号','排序'):return 10
    if name.endswith('ID') or name in ('ASIN','编号','代表ID','比较ID','素材ID','原文ID','原问ID','来源ID'):return 16
    if name in ('问题','问题中译','问句','整理后问句','原问','原文','左原文','右原文','文本','关键词','保留词','原句','原文变体'):return 40
    if name in ('QA回答','回答中译','A+回答','A+中译','描述稿','商品详情','整理文本'):return 48
    if name in ('原因','依据','商品依据','本品依据','待补资料','待确认','选题理由','合并原因','删除原因','备注'):return 28
    if name in ('属性明细','属性依据','清洗短语','不同后缀','左侧差异','右侧差异','左新词','右新词'):return 28
    if name in ('类型','方向','建议','适用性','复核结果','采用结果','模型建议','决定','选题结果','QA已用','人工调整'):return 16
    if name in ('文件','标题','A+副标题','核心词','核心泛词','共同前缀','合并掉的词序变体'):return 32
    return max(12,min(32,sum(2 if ord(c)>127 else 1 for c in header)+2))

def body_row_height(values,widths):
    for value,width in zip(values,widths):
        if value is None:continue
        text=str(value)
        if '\n' in text or sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)>width-2:return 28
    return 14
