// Shared export preference: header first, fixed row height, automatic column widths, no panes.
export function styleTable(sheet,last,bottom,widths,values,headerRow=1){
 const all=sheet.getRange(`A1:${last}${bottom}`);
 all.format.font={name:'SimSun',size:11,color:'#404040'};
 all.format.wrapText=false;
 all.format.verticalAlignment='center';
 if(!widths)all.format.autofitColumns();
 for(let index=0;index<=last.charCodeAt(0)-65;index++){
  const letter=String.fromCharCode(65+index);
  const column=sheet.getRange(`${letter}1:${letter}${bottom}`);
  const width=column.format.columnWidth;
  column.format.columnWidth=widths?widths[index]:Math.min(48,Math.max(10,Number.isFinite(width)?width+2:16));
 }
 all.format.rowHeight=14;
 const matrix=values??all.values;
 // Only stretch rows that need a second line, and never auto-grow long answers.
 let stretch=null;
 for(let row=headerRow+1;row<=bottom+1;row++){
  const needs=row<=bottom&&matrix[row-1]?.some((v,j)=>{
   if(v===null||v===undefined)return false;
   const text=String(v),width=widths?.[j]??sheet.getRange(`${String.fromCharCode(65+j)}1`).format.columnWidth;
   return text.includes('\n')||text.replace(/[^\x00-\xff]/g,'xx').length>width-2;
  });
  if(needs&&stretch===null)stretch=row;
  if(!needs&&stretch!==null){const range=sheet.getRange(`A${stretch}:${last}${row-1}`);range.format.rowHeight=28;range.format.wrapText=true;stretch=null}
 }
 all.format.borders={preset:'all',style:'thin',color:'#D9D9D9'};
 if(bottom>headerRow){
  const body=sheet.getRange(`A${headerRow+1}:${last}${bottom}`);body.format.fill='#FFFFFF';
  body.conditionalFormats.add('expression',{formula:'MOD(ROW(),2)=0',format:{fill:'#F2F2F2'}});
 }
 const header=sheet.getRange(`A${headerRow}:${last}${headerRow}`);
 header.format.rowHeight=16.5;
 header.format.fill='#4472C4';
 header.format.font={name:'Microsoft YaHei',size:11,bold:true,color:'#FFFFFF'};
 header.format.horizontalAlignment='center';
 sheet.showGridLines=false;
 sheet.freezePanes.unfreeze();
}
