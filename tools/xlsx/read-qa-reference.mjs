import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(process.argv[2]));
for(const name of ['客户问答','A+FAQ']){
 const sheet=wb.worksheets.getItem(name);
 console.log(JSON.stringify({sheet:name,rows:sheet.getRange(name==='客户问答'?'A5:K18':'A5:L11').values.map(row=>row.map(v=>typeof v==='string'?v.slice(0,650):v))}));
}
