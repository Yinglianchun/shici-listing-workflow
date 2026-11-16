import fs from 'node:fs/promises';
import { resolve,dirname,join } from 'node:path';
import { SpreadsheetFile,Workbook } from '@oai/artifact-tool';
import { planWorkbook } from '../../xlsx-plan.mjs';
import {styleTable} from './table-style.mjs';

const args=process.argv.slice(2);
const option=name=>args.includes(name)?args[args.indexOf(name)+1]:undefined;
const input=option('--input'),sourceFile=option('--sources'),out=option('--out');
if(!input||!sourceFile||!out)throw new Error('用法：export-grades.mjs --input 分级目录 --sources sources.json --out 结果.xlsx [--render-dir 预览目录]');
if(!args.includes('--overwrite'))try{await fs.stat(out);throw new Error('输出文件已存在，请选择新文件名')}catch(error){if(error.code!=='ENOENT')throw error}
const groups=JSON.parse(await fs.readFile(resolve(input,'graded_groups.json'),'utf8'));
const sources=JSON.parse(await fs.readFile(sourceFile,'utf8'));
const plan=planWorkbook(groups,sources);
const workbook=Workbook.create();
const safe=value=>typeof value==='string'&&value.startsWith('=')?"'"+value:value;
const sheetInfo=[];
for(const [index,definition] of plan.sheets.entries()){
 const sheet=workbook.worksheets.add(definition.name);
 sheet.showGridLines=false;
 const matrix=[definition.headers,...definition.rows].map(row=>row.map(safe));
 const last=String.fromCharCode(64+definition.headers.length);
 const bottom=1+definition.rows.length;
 const range=sheet.getRange(`A1:${last}${bottom}`);
 range.values=matrix;
 styleTable(sheet,last,bottom);
 if(definition.rows.length){
  if(definition.kind!=='source'&&definition.kind!=='core'){
   sheet.getRange(`D2:D${bottom}`).setNumberFormat('0');
   sheet.getRange(`J2:J${bottom}`).conditionalFormats.add('containsText',{text:'待复核',format:{fill:'#FFF0CB',font:{color:'#79540F'}}});
  }
 }
 const table=sheet.tables.add(`A1:${last}${bottom}`,true,`ListingTable${index+1}`);
 table.showFilterButton=true;
 sheetInfo.push({name:definition.name,rows:definition.rows.length,preview:`A1:C${Math.min(bottom,4)}`});
}
workbook.recalculate();
const inspected=await workbook.inspect({kind:'table',range:`'${plan.sheets[0].name}'!A1:E4`,include:'values,formulas',tableMaxRows:4,tableMaxCols:5,maxChars:1500});
await fs.mkdir(dirname(resolve(out)),{recursive:true});
const renders=option('--render-dir');
if(renders){
 await fs.mkdir(renders,{recursive:true});
 for(const info of sheetInfo){
  const preview=await workbook.render({sheetName:info.name,range:info.preview,scale:1,format:'png'});
  await fs.writeFile(join(renders,`${info.name}.png`),new Uint8Array(await preview.arrayBuffer()));
 }
 await fs.writeFile(join(renders,'inspection.txt'),inspected.ndjson||JSON.stringify(inspected));
}
const output=await SpreadsheetFile.exportXlsx(workbook);
await output.save(resolve(out));
console.log(JSON.stringify({output:resolve(out),text_groups:plan.groupCount,source_records:plan.sourceCount,sheets:sheetInfo.map(({name,rows})=>({name,rows}))},null,2));
