import { basename } from 'node:path';

const kindNames={keyword:'关键词',ai_generated_question:'问句',unknown:'其他'};
export function planWorkbook(groups,sources){
  const buckets=new Map(),used=new Set(),seen=new Set();
  const headers=['文本组','原文','核心泛词','新等级','属性明细','来源旧等级','提问方向','ASIN','来源ID','处理状态','复核原因'];
  for(const group of groups){
    if(seen.has(group.group_id))throw new Error('分级结果包含重复文本组');
    seen.add(group.group_id);
    const a=group.assessment;
    const level=Number.isInteger(a?.level)&&a.level>=0?a.level:null;
    const kind=kindNames[group.kind]||'其他';
    const name=level===null?`${kind}待复核`:`${kind}${level}级`;
    if(!buckets.has(name))buckets.set(name,{name,kind,level,headers,rows:[],widths:[13,58,27,9,49,12,20,30,34,15,45]});
    const attributes=(a.attributes||[]).map(attr=>`${attr.labels?.[0]||attr.concept}：${attr.values.join(', ')}`).join('\n');
    buckets.get(name).rows.push([group.group_id,group.text,a.core_term||'',level,attributes,
      (group.source_levels||[]).join(', '),a.topic||'',group.asins.join(', '),group.sources.join(', '),
      level===null?'待复核':'分级建议',(a.grading_reasons||[]).join('；')]);
    for(const id of group.sources)used.add(id);
  }
  const sheets=[...buckets.values()].sort((a,b)=>a.kind.localeCompare(b.kind,'zh-CN')||(a.level??Infinity)-(b.level??Infinity));
  for(const sheet of sheets)sheet.rows.sort((a,b)=>String(a[2]).localeCompare(String(b[2]))||String(a[1]).localeCompare(String(b[1])));
  const cores=new Map();
  for(const group of groups){
    const core=group.assessment?.core_term;
    if(!core)continue;
    const key=core.toLowerCase();
    if(!cores.has(key))cores.set(key,{text:core,groups:0,sources:new Set(),asins:new Set()});
    const item=cores.get(key);item.groups++;
    for(const id of group.sources)item.sources.add(id);
    for(const asin of group.asins)item.asins.add(asin);
  }
  if(cores.size)sheets.unshift({name:'核心泛词',kind:'core',headers:['核心泛词','关联文本组数','来源记录数','涉及ASIN','状态'],
    rows:[...cores.values()].sort((a,b)=>a.text.localeCompare(b.text)).map(item=>[item.text,item.groups,item.sources.size,[...item.asins].sort().join(', '),'0级核心词候选']),widths:[32,17,17,34,25]});
  const sourceMap=new Map(sources.map(source=>[source.source_id,source]));
  const sourceRows=[...used].sort().map(id=>{
    const source=sourceMap.get(id);
    if(!source)throw new Error(`找不到来源记录 ${id}`);
    const raw=source.raw;
    return [id,basename(source.file),source.csv_record,raw.ASIN,raw.Marketplace||'',
      source.kind==='ai_generated_question'?'AI生成问句':source.kind==='keyword'?'关键词':'未知',
      raw.Keyword,raw.CoreTerm||'',/^\d+$/.test(String(raw.Level??''))?Number(raw.Level):raw.Level||'',raw.Type,raw.Evidence||''];
  });
  sheets.push({name:'来源记录',kind:'source',headers:['来源ID','文件名','CSV记录位置','ASIN','站点','来源类型','原始文本','原核心词','原等级','导出原类型','导出所列依据'],rows:sourceRows,widths:[15,49,15,17,9,17,66,28,10,17,65]});
  return {sheets,groupCount:groups.length,sourceCount:sourceRows.length};
}
