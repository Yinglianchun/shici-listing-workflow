import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { targetsFromSources, captureBatch } from './capture-batch.mjs';

test('source records share a target only within a marketplace, keeping source links and own role', () => {
  const records = [['S1','US'], ['S2','US'], ['S3','DE']].map(([source_id, Marketplace]) => ({source_id, raw: {ASIN:'B0BW8JZ279', Marketplace}}));
  const result = targetsFromSources(records, ['B0BW8JZ279']);
  assert.equal(result.length, 2);
  assert.deepEqual(result[0].source_ids, ['S1', 'S2']);
  assert.equal(result[0].role, 'own');
  assert.match(result[1].url, /amazon.de/);
  assert.throws(() => targetsFromSources([{source_id:'S4',raw:{ASIN:'B0BW8JZ279'}}]));
});

test('batch continues after a failure and resume skips only readable successful snapshots', async () => {
  const root = await mkdtemp(join(tmpdir(), 'listing-batch-'));
  try {
    const targets = targetsFromSources(['B0BW8JZ279','B07W52VH1X'].map((ASIN, i) => ({source_id:String(i),raw:{ASIN,Marketplace:'US'}})), ['B0BW8JZ279']);
    const out = join(root, 'batch');
    let calls = [];
    const runCapture = async url => {
      const target = targets.find(t => t.url === url);
      calls.push(target.asin);
      if (target.role === 'own') throw new Error('network unavailable');
      const folder = join(root, target.asin);
      await mkdir(folder, {recursive:true});
      await writeFile(join(folder,'product.json'), JSON.stringify({status:'captured',requested_asin:target.asin,source_url:url}));
      return {folder,status:'captured',title:'Example',missing_sections:[]};
    };
    const first = await captureBatch(targets, {out, runCapture});
    assert.equal(first.summary.failed, 1);
    assert.equal(first.summary.captured, 1);
    calls = [];
    await captureBatch(targets, {out, resume:true, runCapture});
    assert.deepEqual(calls, ['B0BW8JZ279']);
    const index = JSON.parse(await readFile(first.index,'utf8'));
    assert.equal(index.products[0].status, 'failed');
    assert.equal(index.products[1].source_ids[0], '1');
    await rm(join(root,'B07W52VH1X','product.json'));
    calls = [];
    await captureBatch(targets, {out, resume:true, runCapture});
    assert.deepEqual(calls, ['B0BW8JZ279','B07W52VH1X']);
  } finally { await rm(root, {recursive:true,force:true}); }
});
