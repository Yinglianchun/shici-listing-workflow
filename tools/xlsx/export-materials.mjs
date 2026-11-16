import fs from 'node:fs/promises';
import {resolve,dirname,join} from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import {styleTable} from './table-style.mjs';

const args=process.argv.slice(2),option=name=>args.includes(name)?args[args.indexOf(name)+1]:undefined;
const input=option('--input'),out=option('--out'),renders=option('--render-dir');
if(!input||!out)throw new Error('需要 --input materials.json --out 素材.xlsx');
if(!args.includes('--overwrite'))try{await fs.stat(out);throw new Error('输出文件已存在')}catch(e){if(e.code!=='ENOENT')throw e}
const data=JSON.parse(await fs.readFile(input,'utf8'));
const statusNames={eligible:'可用',exclude:'不适用',pending:'待补资料',variant_only:'仅其他已确认子体可用'};
const cell=value=>{
 if(value===null||value===undefined)return '';
 if(typeof value==='object')return Array.isArray(value)?value.map(v=>typeof v==='object'?JSON.stringify(v):String(v)).join('; '):JSON.stringify(value);
 return typeof value==='string'&&value.startsWith('=')?"'"+value:value;
};
const sheets=[];
if(data.core_terms?.length)sheets.push({name:'核心泛词0级',headers:['核心泛词','等级','ASIN','依据'],rows:data.core_terms.map(c=>[c.text,0,c.asin,c.basis])});
for(const [kind,name,field] of [['keyword','关键词','text'],['ai_generated_question','完整问句','text'],['ai_generated_question','清洗短语','phrase']]){
 const buckets=new Map();
 for(const row of data.materials.filter(r=>r.kind===kind)){
  const level=Number.isInteger(row.level)?row.level:null;
  const key=level===null?'待复核':`${level}级`;
  if(!buckets.has(key))buckets.set(key,{level,rows:[]});
  buckets.get(key).rows.push([row.material_id,level,row[field],row.qa_used?'已用':'未用',row.included_in_description?'采用':'未采用',
   row.member_ids.join(', '),row.originals.join('\n'),row.asins.join(', '),row.sources.join(', '),row.basis,row.phrase_status]);
 }
 for(const [key,bucket] of [...buckets].sort((a,b)=>(a[1].level??99)-(b[1].level??99))){
  sheets.push({name:name+key,headers:['素材ID','等级',name,'QA使用情况','描述采用情况','原文ID','全部原文','ASIN','来源ID','商品资料依据','清洗状态'],rows:bucket.rows});
 }
}
sheets.push({name:'不适用及待补资料',headers:['原文ID','类型','原文','适用性建议','原因','缺少资料','来源ID'],rows:data.held_materials.map(g=>[
 g.group_id,g.kind==='keyword'?'关键词':'AI生成问句',g.text,statusNames[g.applicability.status]||'待复核',g.applicability.reason,
 Array.isArray(g.applicability.missing_information)?g.applicability.missing_information.join('; '):'',g.sources.join(', ')])});
if(data.final_reviews)sheets.push({name:'合并前再次自查',headers:['素材ID','原文','清洗后','自查建议','原因','本品依据'],rows:data.final_reviews.map(r=>[r.material.material_id,r.material.text,r.material.phrase,statusNames[r.review.status]||'待复核',r.review.reason,r.review.basis])});
if(data.advertising_keywords)sheets.push({name:'完整广告关键词',headers:['关键词','等级','来源ID'],rows:data.advertising_keywords.map(r=>[r.keyword,r.level,r.sources.join(', ')])});
if(data.prefix_groups)sheets.push({name:'共同前缀整理',headers:['整理文本','共同前缀','不同后缀','完整原句'],rows:data.prefix_groups.map(r=>[r.text,r.prefix,r.suffixes.join('; '),r.members.map(m=>m.text).join('\n')])});
const wb=Workbook.create();
if(renders)await fs.mkdir(renders,{recursive:true});
for(const [index,definition] of sheets.entries()){
 const sheet=wb.worksheets.add(definition.name),last=String.fromCharCode(64+definition.headers.length),bottom=definition.rows.length+1;
 sheet.getRange(`A1:${last}${bottom}`).values=[definition.headers,...definition.rows].map(row=>row.map(cell));
 styleTable(sheet,last,bottom);
 sheet.tables.add(`A1:${last}${bottom}`,true,`Material${index+1}`).showFilterButton=true;
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:`'${sheets[0].name}'!A1:D3`,tableMaxRows:3,tableMaxCols:4,maxChars:1000})).ndjson);
if(renders)for(const definition of sheets){
 const blob=await wb.render({sheetName:definition.name,range:`A1:C${Math.min(definition.rows.length+1,3)}`,scale:1,format:'png'});
 await fs.writeFile(join(renders,`${definition.name}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await fs.mkdir(dirname(resolve(out)),{recursive:true});
await (await SpreadsheetFile.exportXlsx(wb)).save(resolve(out));
console.log(JSON.stringify({output:resolve(out),sheets:sheets.map(s=>({name:s.name,rows:s.rows.length}))}));
