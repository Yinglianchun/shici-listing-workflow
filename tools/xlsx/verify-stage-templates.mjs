import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [folder,output]=process.argv.slice(2);
await fs.mkdir(output,{recursive:true});
const seen=new Set();
for(const file of (await fs.readdir(folder)).filter(n=>n.endsWith('.xlsx'))){
 const input=path.join(folder,file),wb=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
 const info=await wb.inspect({kind:'sheet',include:'id,name',maxChars:12000});
 const names=info.ndjson.split('\n').filter(Boolean).map(l=>JSON.parse(l)).filter(r=>r.kind==='sheet').map(r=>r.name);
 for(let i=0;i<names.length;i++){
  const sheet=wb.worksheets.getItemAt(i),columns=sheet.getUsedRange().values[0];
  if(seen.has(JSON.stringify(columns)))continue;seen.add(JSON.stringify(columns));
  const previewBook=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
  const image=await previewBook.render({sheetName:names[i],range:`A1:${String.fromCharCode(64+columns.length)}5`,scale:1,format:'png'});
  await fs.writeFile(path.join(output,file.replace('.xlsx','')+'-'+names[i]+'.png'),new Uint8Array(await image.arrayBuffer()));
 }
 console.log(JSON.stringify({file,sheets:names.length}));
}
console.log(JSON.stringify({distinctLayouts:seen.size}));
