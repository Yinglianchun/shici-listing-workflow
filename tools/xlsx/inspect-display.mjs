import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output,onlySheet]=process.argv.slice(2);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const sheets=await wb.inspect({kind:'sheet',include:'id,name',maxChars:5000});console.log(sheets.ndjson);
const names=sheets.ndjson.split('\n').filter(Boolean).map(line=>JSON.parse(line)).filter(r=>r.kind==='sheet').map(r=>r.name);
const fixed=names.includes('一级词');
console.log((await wb.inspect({kind:'table',range:(fixed?'一级词!A1:F3':'关键词1级!A1:H3'),include:'values',tableMaxRows:3,tableMaxCols:8,tableMaxCellChars:140,maxChars:2400})).ndjson);
for(const [name,range] of fixed?names.map(name=>[name,'A1:F3']):[['关键词1级','C1:H3'],['问句1级','C1:H2']]){
 if(onlySheet&&name!==onlySheet)continue;
 const renderBook=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
 const picture=await renderBook.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(output+'-'+name+'.png',new Uint8Array(await picture.arrayBuffer()));
}
