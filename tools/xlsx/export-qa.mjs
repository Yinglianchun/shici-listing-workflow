import fs from 'node:fs/promises';
import {resolve,dirname,join} from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import {styleTable} from './table-style.mjs';

const args=process.argv.slice(2);
const option=name=>args.includes(name)?args[args.indexOf(name)+1]:undefined;
const input=option('--input'),out=option('--out'),renders=option('--render-dir');
if(!input||!out)throw new Error('需要 --input qa_selection.json --out QA.xlsx');
if(!args.includes('--overwrite'))try{await fs.stat(out);throw new Error('输出文件已存在')}catch(e){if(e.code!=='ENOENT')throw e}
const data=JSON.parse(await fs.readFile(input,'utf8'));
const string=value=>Array.isArray(value)?value.join('\n'):typeof value==='string'?value:'';
const headers=['编号','提问方向','英文问句','中文问句','QA英文回答','QA中文译文','A+英文副标题','A+英文回答','A+中文译文','商品资料依据','待确认事项','关联原问ID','选题理由','复核意见'];
const rows=data.qa.map(q=>[q.qa_id,q.topic,q.question_en,q.question_zh,q.answer_en||q.status,q.answer_zh||q.status,q.aplus_subtitle_en,q.aplus_answer_en||q.status,q.aplus_answer_zh||q.status,q.basis,q.pending_questions,
 q.answer_en?q.covered_question_ids.map(i=>`覆盖建议：${i}`):q.candidate_question_ids.map(i=>`选题来源：${i}`),q.reason,''].map(string));
const wb=Workbook.create(),sheet=wb.worksheets.add('QA选题与回答');
const bottom=1+rows.length;
const range=sheet.getRange(`A1:N${bottom}`);
range.values=[headers,...rows].map(row=>row.map(v=>v.startsWith('=')?"'"+v:v));
styleTable(sheet,'N',bottom);
sheet.getRange(`N2:N${bottom}`).format.fill='#FFF4DC';
sheet.tables.add(`A1:N${bottom}`,true,'QaSelection').showFilterButton=true;
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'QA选题与回答!A1:D3',include:'values',tableMaxRows:3,tableMaxCols:4,maxChars:1000})).ndjson);
if(renders){
 await fs.mkdir(renders,{recursive:true});
 for(const [name,range] of [['qa','A1:D4'],['answers','E1:F4'],['last',`A${Math.max(1,bottom-2)}:D${bottom}`]]){
  const blob=await wb.render({sheetName:sheet.name,range,scale:1,format:'png'});
  await fs.writeFile(join(renders,`${name}.png`),new Uint8Array(await blob.arrayBuffer()));
 }
}
await fs.mkdir(dirname(resolve(out)),{recursive:true});
await (await SpreadsheetFile.exportXlsx(wb)).save(resolve(out));
console.log(JSON.stringify({output:resolve(out),qa:rows.length}));
