import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const folder=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
await fs.mkdir(output,{recursive:true});
const status=JSON.parse(await fs.readFile(path.join(folder,'status.json'),'utf8'));
const extras=(await fs.readdir(folder)).filter(n=>n.includes('05_问句与分级明细')&&n.endsWith('_输出整理版.xlsx'));
let files=[status.steps[2].file,...status.steps.slice(4).map(s=>s.file),...extras];
if(process.argv[4]==='all'){
 files=(await fs.readdir(folder)).filter(n=>n.endsWith('.xlsx')&&!n.startsWith('~$'));
 try{files.push(...(await fs.readdir(path.join(folder,'表格'))).filter(n=>n.endsWith('.xlsx')&&!n.startsWith('~$')).map(n=>path.join('表格',n)))}catch(e){if(e.code!=='ENOENT')throw e}
}
for(const file of files.filter(n=>!process.argv[4]||process.argv[4]==='all'||new RegExp(process.argv[4]).test(n))){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(folder,file)));
 for(const sheet of wb.worksheets.items){
  const matrix=sheet.getUsedRange().values;
  console.log(JSON.stringify({file,sheet:sheet.name,rows:matrix.length-1,columns:matrix[0],widthA:sheet.getRange('A1').format.columnWidth,height:sheet.getRange('A2').format.rowHeight}));
  const last=String.fromCharCode(64+matrix[0].length);
  const picture=await wb.render({sheetName:sheet.name,range:`A1:${last}${Math.min(3,matrix.length)}`,scale:1,format:'png'});
  await fs.writeFile(path.join(output,path.basename(file).replace('.xlsx','')+'-'+sheet.name+'.png'),new Uint8Array(await picture.arrayBuffer()));
 }
}
