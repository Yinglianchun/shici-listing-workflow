import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import {styleTable} from './table-style.mjs';
const args=process.argv.slice(2),get=n=>args[args.indexOf(n)+1];
const sheets=JSON.parse(await fs.readFile(get('--input'),'utf8')),wb=Workbook.create();
const cell=v=>v===null||v===undefined?'':typeof v==='object'?JSON.stringify(v):typeof v==='string'&&v.startsWith('=')?"'"+v:v;
for(const [i,d] of sheets.entries()){
 const rows=d.rows.length?d.rows:Array.from({length:d.template_rows||0},()=>d.headers.map(()=>null));
 const s=wb.worksheets.add(d.name),last=String.fromCharCode(64+d.headers.length),header=d.header_row||1,bottom=rows.length+header;
 const preamble=Array.from({length:header-1},(_,n)=>d.headers.map((_,j)=>j===0?(n===0?d.title||'':n===1?d.note||'':''):''));
 const matrix=[...preamble,d.headers,...rows].map(r=>r.map(cell));
 s.getRange(`A1:${last}${bottom}`).values=matrix;
 const table=s.tables.add(`A${header}:${last}${bottom}`,true,`StageTable${i+1}`);table.showFilterButton=true;table.style='TableStyleLight1';
 styleTable(s,last,bottom,d.column_widths,matrix,header);
 if(header>1){
  const h=s.getRange(`A${header}:${last}${header}`);h.format.fill='#4472C4';h.format.font={name:'Microsoft YaHei',size:11,bold:true,color:'#FFFFFF'};h.format.rowHeight=16.5;
  const title=s.getRange(`A1:${last}1`);title.merge();title.format.fill='#FFFFFF';title.format.font={name:'Microsoft YaHei',size:13,bold:true,color:'#333333'};title.format.rowHeight=24;
  if(header>2){const note=s.getRange(`A2:${last}2`);note.merge();note.format.wrapText=true;note.format.rowHeight=28;}
 }
 if(d.layout==='description'){
  const column=s.getRange(`A1:A${bottom}`);column.format.autofitColumns();
  column.format.columnWidth=Math.min(255,column.format.columnWidth);
  const body=s.getRange(`A2:${last}${bottom}`);body.format.wrapText=true;body.format.verticalAlignment='top';body.format.autofitRows();
 }
}
wb.recalculate();
await (await SpreadsheetFile.exportXlsx(wb)).save(get('--out'));
