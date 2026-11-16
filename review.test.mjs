import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright-core';

test('review page filters, confirms, undoes, imports and exports without changing source', async () => {
  const root=await mkdtemp(join(tmpdir(),'listing-review-'));
  let browser;
  try {
    const rows=[
      {left:'L',right:'R',left_text:'Do these glasses fit small faces? </script><script>window.injected=true</script>',right_text:'Do these glasses fit large faces?',relation:'same_topic',status:'needs_review',score:.95,left_unique:['小脸'],right_unique:['大脸'],left_evidence:['small faces'],right_evidence:['large faces'],reason:'脸型不同',topics:['尺寸与适配']},
      {left:'C',right:'D',left_text:'Do they block UV?',right_text:'Do they protect against UV rays?',relation:'equivalent',status:'needs_review',score:.97,left_unique:[],right_unique:[],reason:'同义改写',topics:['紫外线防护']}
    ];
    const original=JSON.stringify(rows);
    await writeFile(join(root,'judgments.json'),original);
    await writeFile(join(root,'summary.json'),JSON.stringify({model:'test-only'}));
    const built=spawnSync('C:\\Python313\\python.exe',['review.py','--input',root],{cwd:process.cwd(),encoding:'utf8'});
    assert.equal(built.status,0,built.stderr);
    browser=await chromium.launch({channel:'chrome'});
    const page=await browser.newPage({viewport:{width:1200,height:900}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(join(root,'review.html')).href);
    assert.equal(await page.locator('.pair').count(),2);
    assert.equal(await page.evaluate(()=>window.injected),undefined);
    await page.locator('#search').fill('UV');
    assert.equal(await page.locator('.pair').count(),1);
    await page.locator('#search').fill('');
    await page.locator('.pair').first().getByRole('button',{name:'确认这条关系'}).click();
    await page.locator('#state').selectOption('confirmed');
    assert.equal(await page.locator('.pair').count(),1);
    const downloadPromise=page.waitForEvent('download');
    await page.locator('#download').click();
    const download=await downloadPromise;
    const exported=JSON.parse(await readFile(await download.path(),'utf8'));
    assert.equal(exported.decisions.length,1);
    assert.equal(exported.decisions[0].relation,'same_topic');
    assert.equal(exported.decisions[0].left_text,rows[0].left_text);
    await page.locator('.pair').first().getByRole('button',{name:'撤销确认'}).click();
    assert.equal(await page.locator('.pair').count(),0);
    const imported=join(root,'decisions.json');await writeFile(imported,JSON.stringify(exported));
    await page.locator('#import-file').setInputFiles(imported);
    await page.locator('.pair').first().waitFor();
    assert.match(await page.locator('#storage').textContent(),/已导入 1 条/);
    assert.equal(await readFile(join(root,'judgments.json'),'utf8'),original);
    assert.deepEqual(errors,[]);
  } finally {
    if(browser)await browser.close();
    assert.equal(dirname(resolve(root)),resolve(tmpdir()));
    await rm(root,{recursive:true,force:true});
  }
});
