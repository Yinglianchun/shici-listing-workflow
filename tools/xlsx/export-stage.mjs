import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import {styleTable} from './table-style.mjs';
const args=process.argv.slice(2),get=n=>args[args.indexOf(n)+1];
const sheets=JSON.parse(await fs.readFile(get('--input'),'utf8')),wb=Workbook.create();
const cell=v=>v===null||v===undefined?'':typeof v==='object'?JSON.stringify(v):typeof v==='string'&&v.startsWith('=')?"'"+v:v;
for(const [i,d] of sheets.entries()){
 const rows=d.rows.length?d.rows:Array.from({length:d.template_rows||0},()=>d.headers.map(()=>null));
 const s=wb.worksheets.add(d.name),last=String.fromCharCode(64+d.headers.length),bottom=rows.length+1;
 s.getRange(`A1:${last}${bottom}`).values=[d.headers,...rows].map(r=>r.map(cell));
 const table=s.tables.add(`A1:${last}${bottom}`,true,`StageTable${i+1}`);table.showFilterButton=true;table.style='TableStyleLight1';
 styleTable(s,last,bottom,d.column_widths,[d.headers,...rows]);
 if(d.layout==='description'){
  const column=s.getRange(`A1:A${bottom}`);column.format.autofitColumns();
  column.format.columnWidth=Math.min(255,column.format.columnWidth);
  const body=s.getRange(`A2:${last}${bottom}`);body.format.wrapText=true;body.format.verticalAlignment='top';body.format.autofitRows();
 }
}
wb.recalculate();
await (await SpreadsheetFile.exportXlsx(wb)).save(get('--out'));
