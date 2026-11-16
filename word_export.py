"""Portable Word description export; no extra runtime installation required."""
from xml.sax.saxutils import escape
from zipfile import ZipFile,ZIP_DEFLATED


def export_description(text,path,asin,limit=9000):
    text=' '.join(text.split())
    if len(text)>limit:raise ValueError('描述超过本次字符上限，请重新组合完整素材')
    def paragraph(value,bold=False):
        return '<w:p>'+('<w:pPr><w:pStyle w:val="Title"/></w:pPr>' if bold else '')+'<w:r><w:t xml:space="preserve">'+escape(str(value))+'</w:t></w:r></w:p>'
    ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    document=f'<w:document xmlns:w="{ns}"><w:body>'+paragraph(asin+' 商品描述素材',True)+paragraph(f'{len(text)} / {limit} characters')+paragraph(text)+'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml',document)
        z.writestr('word/_rels/document.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('word/styles.xml',f'<w:styles xmlns:w="{ns}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style></w:styles>')
    return path
