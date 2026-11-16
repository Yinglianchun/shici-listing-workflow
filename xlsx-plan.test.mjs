import { test } from 'node:test';
import assert from 'node:assert/strict';
import { planWorkbook } from './xlsx-plan.mjs';

test('zero level and unresolved level stay separate; every source retained once',()=>{
 const groups=[
  {group_id:'G1',text:'sunglasses',kind:'keyword',sources:['S1','S2'],asins:['OWN','COMP'],source_levels:['0'],assessment:{core_term:'sunglasses',level:0,attributes:[],grading_reasons:[]}},
  {group_id:'G2',text:'titanium sunglasses',kind:'keyword',sources:['S3'],asins:['COMP'],source_levels:['1'],assessment:{core_term:'sunglasses',level:null,attributes:[],grading_reasons:['材质未识别']}}
 ];
 const sources=['S1','S2','S3'].map((source_id,i)=>({source_id,file:'source.csv',csv_record:i+2,kind:'keyword',raw:{ASIN:'OWN',Keyword:'raw '+i,Type:'关键词'}}));
 const result=planWorkbook(groups,sources);
 assert.equal(result.groupCount,2);
 assert.equal(result.sourceCount,3);
 assert.equal(result.sheets.find(s=>s.name==='关键词0级').rows[0][3],0);
 assert.equal(result.sheets.find(s=>s.name==='关键词待复核').rows[0][3],null);
 assert.equal(result.sheets[0].name,'核心泛词');
 assert.equal(result.sheets.at(-1).rows.length,3);
 assert.equal(groups[1].assessment.level,null);
});

test('missing source references cannot silently disappear from export',()=>{
 const group={group_id:'G',text:'term',kind:'keyword',sources:['missing'],asins:['ASIN'],assessment:{level:1,attributes:[]}};
 assert.throws(()=>planWorkbook([group],[]),/找不到来源/);
});
