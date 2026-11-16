import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [file,output]=process.argv.slice(2);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1800})).ndjson);
for(const sheet of wb.worksheets.items){
 const values=sheet.getUsedRange().values;
 console.log(JSON.stringify({sheet:sheet.name,rows:values.length,firstRows:values.slice(0,3).map(row=>row.map(v=>typeof v==='string'?v.slice(0,180):v))}));
 if(output){
  await fs.mkdir(output,{recursive:true});
  const last=String.fromCharCode(64+values[0].length);
  const preview=await wb.render({sheetName:sheet.name,range:`A1:${last}${Math.min(values.length,4)}`,scale:1,format:'png'});
  await fs.writeFile(path.join(output,sheet.name+'.png'),new Uint8Array(await preview.arrayBuffer()));
 }
}
