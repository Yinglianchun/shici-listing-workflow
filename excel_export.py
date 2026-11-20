"""Stage workbooks. Use the local artifact runtime; portable OOXML fallback for other PCs."""
import json
import math
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile,ZIP_DEFLATED
from table_layout import compact_header,column_width,body_row_height
from naming import named_file,plan_file

FIELD_NAMES={'concept':'属性类别','values':'取值','labels':'属性名称','evidence':'原文依据',
    'status':'状态','reason':'原因','qa_id':'QA编号','question_id':'原问ID','group_id':'原文ID',
    'basis':'本品依据','missing_information':'待补资料','type':'类型','source_id':'来源ID',
    'text':'原文','left':'左侧ID','right':'右侧ID','relation':'关系','source':'来源'}
VALUE_NAMES={'eligible':'可用','pending':'待补资料','exclude':'不适用','variant_only':'仅其他已确认子体',
    'equivalent':'同义重复','partial_overlap':'部分重合','same_topic':'仅同主题','different':'不同',
    'uncertain':'不确定','unjudged':'尚未判断','keyword':'关键词','ai_generated_question':'AI生成问句'}
ENUM_HEADERS={'建议','自查建议','复核建议','原模型建议','模型原建议','采用建议','关系','关系建议','本品适用性','类型','选题状态','本品事实判断','投放处理','文案处理'}


def readable(value):
    """Reader-facing text; the original objects remain in stage JSON and raw plans."""
    if value is None:return ''
    if isinstance(value,bool):return '是' if value else '否'
    if isinstance(value,list):return '；'.join(str(readable(item)) for item in value if item is not None and item!='')
    if isinstance(value,dict):
        if 'concept' in value and 'values' in value:
            label=readable(value.get('labels')) or str(value['concept'])
            return label+'：'+str(readable(value['values']))
        return '；'.join(FIELD_NAMES.get(k,k)+'：'+str(VALUE_NAMES.get(v,v) if isinstance(v,str) else readable(v)) for k,v in value.items() if v is not None and v!='' and v!=[])
    return value


def attribute_evidence(attributes):
    if not isinstance(attributes,list):return ''
    return '；'.join(str(readable(a.get('evidence',[]))) for a in attributes if isinstance(a,dict) and a.get('evidence'))


def presentation_sheets(sheets,translate=True):
    expanded=[]
    for s in sheets:
        # QA and A+ are different destinations. Keep their long bilingual text apart.
        if s['name']=='QA选题与回答' and 'A+英文回答' in s['headers']:
            h=s['headers']
            specs=[('QA选题与回答',['编号','方向','英文问题','中文问题','QA英文回答','中文译文','本品依据','待补资料']),
                ('A+回答',['编号','英文问题','A+副标题','A+英文回答','A+中文译文','本品依据','待补资料']),
                ('原问关联',['编号','方向','选择理由','实际覆盖原问ID','候选原问ID'])]
            if '依据' in h and '本品依据' not in h:
                specs=[(name,['依据' if v=='本品依据' else v for v in headers]) for name,headers in specs]
            used={v for _,headers in specs for v in headers}
            specs[-1][1].extend(v for v in h if v not in used)
            for name,headers in specs:
                present=[v for v in headers if v in h]
                expanded.append({**s,'name':name,'headers':present,'rows':[[row[h.index(v)] for v in present] for row in s['rows']]})
        else:expanded.append(s)
    output=[]
    for s in expanded:
        headers=list(s['headers']);attribute=next((i for i,h in enumerate(headers) if h in ('属性','独立属性')),None) if '属性原文依据' not in headers else None
        rows=[]
        for row in s['rows']:
            values=[]
            for i,value in enumerate(row):
                cell=readable(value)
                if translate and headers[i] in ENUM_HEADERS and isinstance(cell,str):cell=VALUE_NAMES.get(cell,cell)
                values.append(cell)
            if attribute is not None:values.insert(attribute+1,attribute_evidence(row[attribute]))
            rows.append(values)
        if attribute is not None:headers.insert(attribute+1,'属性原文依据')
        if s.get('layout') not in ('keyword_reference','master_reference'):headers=[compact_header(h) for h in headers]
        level_column=next((i for i,h in enumerate(headers) if h in ('等级','属性数')),None)
        if level_column is not None:
            rows.sort(key=lambda row:row[level_column] if isinstance(row[level_column],(int,float)) else 999)
            if '序号' in headers:
                position=headers.index('序号')
                for number,row in enumerate(rows,1):row[position]=number
        widths=s.get('column_widths') or [column_width(h) for h in headers]
        if s.get('layout')=='description':widths=[255,*widths[1:]]
        output.append({**s,'headers':headers,'rows':rows,'column_widths':widths})
    def sheet_level(s):
        name=s['name']
        if name.startswith('L0'):return 0
        match=re.search(r'(\d+)级',name)
        if match:return int(match[1])
        for n,prefix in enumerate(['一级','二级','三级','四级'],1):
            if name.startswith(prefix):return n
        return 999
    return output if any(s.get('layout')=='master_reference' for s in output) else sorted(output,key=sheet_level)


def portable_excel(sheets,path):
    """Dependency-free recipient runtime, for PCs without the Codex spreadsheet runtime."""
    sheets=presentation_sheets(sheets)
    header_fill='FF4472C4';body_font='SimSun';font_size=11
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    def col(n):
        value=''
        while n:n,r=divmod(n-1,26);value=chr(65+r)+value
        return value
    def text(v):
        if v is None:return ''
        if isinstance(v,(list,dict)):return str(readable(v))
        return str(v)
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        types=['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>','<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        book=[];rels=[]
        for index,sheet in enumerate(sheets,1):
            data=sheet['rows'] or [[None]*len(sheet['headers']) for _ in range(sheet.get('template_rows',0))]
            header_row=sheet.get('header_row',1)
            preamble=[[sheet.get('title','')],[sheet.get('note','')]] if header_row>1 else []
            preamble=(preamble+[[] for _ in range(header_row)])[:header_row-1]
            matrix=[*preamble,sheet['headers'],*data];cols=len(sheet['headers'])
            widths=sheet['column_widths']
            rows=[]
            for r,row in enumerate(matrix,1):
                cells=[]
                for c,value in enumerate(row,1):
                    ref=f'{col(c)}{r}';style='1' if r==header_row else '2' if r%2==0 else '0'
                    if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):
                        cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
                    else:
                        value=''.join(ch for ch in text(value) if ord(ch)>=32 or ch in '\t\n\r')
                        cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>')
                height=16.5 if r==header_row else body_row_height(row,widths)
                if r>header_row and sheet.get('layout')=='description':height=max(14,math.ceil(len(text(row[0]))/253)*14)
                rows.append(f'<row r="{r}" ht="{height}" customHeight="1">'+''.join(cells)+'</row>')
            xml=f'<worksheet xmlns="{ns}"><cols>'+''.join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i,w in enumerate(widths,1))+'</cols><sheetData>'+''.join(rows)+f'</sheetData><autoFilter ref="A{header_row}:{col(cols)}{len(matrix)}"/></worksheet>'
            z.writestr(f'xl/worksheets/sheet{index}.xml',xml)
            name=escape(sheet['name'],{'"':'&quot;'})
            book.append(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>')
            rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
            types.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'+''.join(types)+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(book)+'</sheets></workbook>')
        rels.append('<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(rels)+'</Relationships>')
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="{font_size}"/><name val="{body_font}"/></font><font><b/><sz val="{font_size}"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="{header_fill}"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F2"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center" wrapText="1"/></xf><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment horizontal="center" vertical="center"/></xf><xf fontId="0" fillId="3" borderId="0" xfId="0"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def delivery_sheets(sheets,filename):
    """Apply the four-workbook reader layout without changing calculation plans."""
    kind=next((k for k in ('本品资料与页面改动建议','QA与A+问答','投放分级关键词与问句','描述素材') if k in str(filename)),None)
    if kind is None:return sheets
    descriptions={
        '本品资料与页面改动建议':[
            ['用途','确认本品、主推子体、核心词和页面改动；后续判断以已确认资料为依据。'],
            ['怎么填写','在聊天补充本块缺项，发“1”开始。确认结果由agent写回“确认表单”。'],
            ['放在哪里用','五点修改建议、需同步的页面字段供更新标题、五点、参数或图片时使用；建议不是已发布内容。']],
        'QA与A+问答':[
            ['用途','按具体关注点准备主QA、备选和A+问答，卖家角度回答并解释具体理由。'],
            ['主QA放哪里','主QA填商品QA区。问题和回答按本品资料重新撰写，英文回答最多250字符。'],
            ['A+放哪里','英文回答最多500字符，供A+可编辑问答/FAQ区域；副标题与对应答案一起使用。'],
            ['其他页怎么用','备选供替换和补充；中文译文供核对；原问关联、完整原问池供选题，不直接整池粘贴。']],
        '投放分级关键词与问句':[
            ['用途','整理用于投放的分级关键词及由问句提炼的关键表达。'],
            ['用哪一列','Keyword为实际广告表达，原问句只供核对；每条广告词完整独立使用。'],
            ['Modifiers怎么写','按表达顺序填写计级的英文限定词，用 + 连接，例如 90s + for women + lightweight。'],
            ['等级怎么用','核心0级，核心外每个独立语义限定加1；0/1级按本项目作为精准否定候选，其余依已确认投放策略使用。'],
            ['排除页怎么用','本次投放排除、事实不符和其他子体备用分开处理；不把本次不投自动当否定词。']],
        '描述素材':[
            ['用途','将已筛选的关键表达整理为商品描述素材组。'],
            ['放在哪里','供后台商品描述字段使用，按目标父体/子体分别选择；不替代QA或A+回答。'],
            ['怎么选择','每组最多9000字符，按表中适用范围及目标ASIN分配；超限分多组，不重复凑字。'],
            ['明细怎么用','描述稿按采用明细的顺序逐条原样拼接，条目间只加分号和空格。']]}
    descriptions[kind].append(['开始本块','四块依次为本品资料、投放词句、QA与A+、描述素材。每块先在聊天核对材料，补齐后发“1”。块内连续执行，完成后等待下一块。'])
    guide={'name':'使用说明','headers':['项目','说明'],'rows':descriptions[kind],
           'header_row':1,'column_widths':[22,96],'layout':'master_reference'}
    removed={'Level(源表)','出现ASIN数','涉及ASIN','涉及ASIN/来源'}
    result=[guide]
    for s in sheets:
        if s['name']=='使用说明':continue
        keep=[i for i,h in enumerate(s['headers']) if h not in removed]
        updated={**s,'header_row':1,'headers':[s['headers'][i] for i in keep],
                 'rows':[[r[i] if i<len(r) else '' for i in keep] for r in s.get('rows',[])]}
        if s.get('column_widths'):updated['column_widths']=[s['column_widths'][i] for i in keep]
        result.append(updated)
    return result


def export_excel(sheets,path):
    path=Path(path);path=named_file(path.parent,path.name);path.parent.mkdir(parents=True,exist_ok=True)
    sheets=delivery_sheets(sheets,path.name)
    runtime=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    plan=plan_file(path);plan.write_text(json.dumps(sheets,ensure_ascii=False),encoding='utf-8')
    if runtime.exists() and (Path(__file__).parent/'tools/xlsx/node_modules').exists():
        with tempfile.TemporaryDirectory(prefix='listing-excel-') as temp:
            display=Path(temp)/'display.json';display.write_text(json.dumps(presentation_sheets(sheets),ensure_ascii=False),encoding='utf-8')
            subprocess.run([str(runtime),str(Path(__file__).parent/'tools/xlsx/export-stage.mjs'),'--input',str(display),'--out',str(path)],check=True)
    else:portable_excel(sheets,path)
    return path
