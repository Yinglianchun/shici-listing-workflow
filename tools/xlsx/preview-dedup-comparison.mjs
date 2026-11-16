import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const file=process.argv[2],folder=path.dirname(file);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1800})).ndjson);
for(const [sheetName,range] of [['批次表现','A1:J6'],['逐条对比','A1:H6'],['删除明细','A1:H6'],['抽样复核','A1:F6']]){
 const preview=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(path.join(folder,sheetName+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
