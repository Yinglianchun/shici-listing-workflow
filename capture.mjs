import { chromium } from 'playwright-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export function productUrl(input, domain = 'www.amazon.com') {
  if (/^[A-Z0-9]{10}$/i.test(input)) input = `https://${domain}/dp/${input}`;
  const url = new URL(input);
  if (url.protocol !== 'https:' || !/^(www\.)?amazon\.(com|co\.uk|de|fr|it|es|ca|com\.au|co\.jp)$/.test(url.hostname) || url.username || url.password || url.port)
    throw new Error('请输入 Amazon 商品详情链接或 10 位 ASIN');
  const asin = url.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:\/|$)/i)?.[1]?.toUpperCase();
  if (!asin) throw new Error('链接中没有商品 ASIN');
  return { asin, url: `https://${url.hostname}/dp/${asin}` };
}

// Runs in the browser against the rendered product page.
export function extractProduct() {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const text = selector => clean(document.querySelector(selector)?.innerText);
  const content = el => {
    if (!el) return '';
    const copy = el.cloneNode(true);
    copy.querySelectorAll('script,style,noscript,template').forEach(node => node.remove());
    return clean(copy.textContent);
  };
  const pairs = selector => [...document.querySelectorAll(selector)].map(row => {
    const cells = [...row.querySelectorAll('th,td')].map(content);
    return cells.length >= 2 ? { name: cells[0], value: cells.slice(1).join(' ') } : null;
  }).filter(Boolean);
  const sections = selector => [...new Set([...document.querySelectorAll(selector)].map(content).filter(Boolean))];
  const aplusNodes = [...document.querySelectorAll('#aplus, #aplus_feature_div')];
  const aplusRoots = aplusNodes.filter(node => !aplusNodes.some(other => other !== node && other.contains(node)));
  return {
    title: text('#productTitle'),
    selected_asin: document.querySelector('input#ASIN')?.value || '',
    price_text: text('#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen') || text('#corePrice_feature_div .a-price .a-offscreen'),
    bullets: sections('#feature-bullets li .a-list-item, #productFactsDesktopExpander .product-facts-title ~ ul > li > .a-list-item'),
    description: text('#productDescription'),
    overview: pairs('#productOverview_feature_div tr'),
    specifications: pairs('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, .product-facts-detail tr, table.voyager-ns-desktop-table tr, table.prodDetTable tr'),
    detail_bullets: sections('#detailBullets_feature_div li'),
    aplus_text: [...new Set(aplusRoots.map(content).filter(Boolean))].join('\n'),
    aplus_text_scope: 'DOM text including collapsed sections, excluding scripts and styles; image text is not extracted.',
    aplus_images: [...document.querySelectorAll('#aplus img, #aplus_feature_div img')].map(el => ({url: el.currentSrc || el.src, alt: el.alt})),
    variants: [...document.querySelectorAll('#twister li[data-asin], #twister li[data-defaultasin]')].map(el => ({
      asin: el.dataset.asin || el.dataset.defaultasin,
      label: clean(el.getAttribute('title') || el.innerText || el.querySelector('img')?.alt),
      selected: el.classList.contains('swatchSelect')
    })),
    images: [...document.querySelectorAll('#altImages img')].map(el => ({url: el.src, alt: el.alt}))
  };
}

export async function capture(input, { out = 'output/products', headed = false, domain } = {}) {
  const target = productUrl(input, domain);
  const folder = resolve(out, `${target.asin}-${new Date().toISOString().replaceAll(':', '-')}`);
  await mkdir(folder, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: !headed });
  let page;
  try {
    page = await browser.newPage({ locale: 'en-US' });
    const response = await page.goto(target.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const title = page.locator('#productTitle');
    await title.waitFor({ timeout: 20000 }).catch(() => {});
    // Trigger lazy-loaded content without opening another product or submitting forms.
    await page.evaluate(async () => {
      for (let i = 0; i < 10; i++) {
        window.scrollBy(0, 900);
        await new Promise(r => setTimeout(r, 150));
      }
      window.scrollTo(0, 0);
    });
    const data = await page.evaluate(extractProduct);
    const body = await page.locator('body').innerText();
    const blocked = /enter the characters you see|type the characters you see|robot check|sorry, we just need to make sure/i.test(body);
    let actual;
    try { actual = productUrl(page.url()); } catch { actual = null; }
    const mismatch = !actual || actual.asin !== target.asin || (data.selected_asin && data.selected_asin !== target.asin);
    const status = blocked ? 'blocked' : mismatch ? 'asin_mismatch' : !data.title || (response?.status() ?? 0) >= 400 ? 'failed' : !data.bullets.length || !data.specifications.length ? 'partial' : 'captured';
    const result = {
      requested_asin: target.asin, marketplace: new URL(target.url).hostname,
      source_url: page.url(), captured_at: new Date().toISOString(), http_status: response?.status(), status,
      source_type: 'listing_claim', ...data,
      missing_sections: ['bullets', 'specifications'].filter(k => !data[k]?.length),
      optional_absent_sections: ['description', 'aplus_text'].filter(k => !data[k]?.length),
      scope: 'Current page DOM, including collapsed specification and A+ text. Variant links are not separately fetched; images are not OCRed. No community QA or reviews collection.'
    };
    await writeFile(resolve(folder, 'page.html'), await page.content(), 'utf8');
    await writeFile(resolve(folder, 'product.json'), JSON.stringify(result, null, 2), 'utf8');
    if (!['captured', 'partial'].includes(status)) throw new Error(`采集未成功：${status}，诊断已保存到 ${folder}`);
    return { folder, title: data.title, status, missing_sections: result.missing_sections };
  } catch (error) {
    await writeFile(resolve(folder, 'error.json'), JSON.stringify({message: error.message, requested_asin: target.asin, url: page?.url()}, null, 2));
    error.folder = folder;
    throw error;
  } finally { await browser.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  const option = name => args.includes(name) ? args[args.indexOf(name) + 1] : undefined;
  try {
    if (!args[0]) throw new Error('用法：npm run capture -- ASIN或链接 [--headed] [--out 目录] [--domain www.amazon.de]');
    console.log(JSON.stringify(await capture(args[0], {out: option('--out'), headed: args.includes('--headed'), domain: option('--domain')}), null, 2));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
