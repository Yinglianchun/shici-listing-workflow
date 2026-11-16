import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { productUrl, extractProduct } from './capture.mjs';

test('ASIN and marketplace links are parsed without accepting other hosts', () => {
  assert.equal(productUrl('b0bw8jz279').asin, 'B0BW8JZ279');
  assert.equal(productUrl('https://www.amazon.de/example/dp/B0BW8JZ279/ref=test?tag=x').url, 'https://www.amazon.de/dp/B0BW8JZ279');
  assert.throws(() => productUrl('https://www.amazon.com.attacker.test/dp/B0BW8JZ279'));
  assert.throws(() => productUrl('https://www.amazon.com/dp/B0BW8JZ279extra'));
});

test('extracts title, spec values, A+ and variant identities from actual DOM', async () => {
  const browser = await chromium.launch({channel: 'chrome'});
  try {
    const page = await browser.newPage();
    await page.setContent(`<span id="productTitle"> Example glasses </span><input id="ASIN" value="B0BW8JZ279">
      <div id="feature-bullets"><ul><li><span class="a-list-item">UV400 lenses</span></li></ul></div>
      <table id="productDetails_techSpec_section_1" style="display:none"><tr><th>Frame width</th><td>142 mm</td></tr></table>
      <table class="prodDetTable" style="display:none"><tr><th>Polarization Type</th><td>Non-Polarized</td></tr></table>
      <div id="productFactsDesktopExpander"><h3 class="product-facts-title">About this item</h3><ul><li><span class="a-list-item">Metal frame</span></li></ul></div>
      <div id="aplus"><p>Brand story</p></div><div id="aplus_feature_div"><div id="aplus"><p style="display:none">Yellow to brown</p><script type="application/json">{"noise":true}</script><img src="https://example.com/image.jpg" alt="Dimensions"></div></div>
      <div id="twister"><ul><li data-asin="B07W52VH1X" title="Yellow"></li></ul></div>`);
    const result = await page.evaluate(extractProduct);
    assert.equal(result.title, 'Example glasses');
    assert.equal(result.selected_asin, 'B0BW8JZ279');
    assert.deepEqual(result.specifications, [{name:'Frame width',value:'142 mm'}, {name:'Polarization Type',value:'Non-Polarized'}]);
    assert.deepEqual(result.bullets, ['UV400 lenses', 'Metal frame']);
    assert.equal(result.aplus_text, 'Brand story\nYellow to brown');
    assert.equal(result.aplus_images[0].alt, 'Dimensions');
    assert.equal(result.variants[0].asin, 'B07W52VH1X');
  } finally { await browser.close(); }
});
