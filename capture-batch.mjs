import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { capture, productUrl } from './capture.mjs';

const domains = { US: 'www.amazon.com', UK: 'www.amazon.co.uk', GB: 'www.amazon.co.uk', DE: 'www.amazon.de', FR: 'www.amazon.fr', IT: 'www.amazon.it', ES: 'www.amazon.es', CA: 'www.amazon.ca', AU: 'www.amazon.com.au', JP: 'www.amazon.co.jp' };
const markets = Object.fromEntries(Object.entries(domains).map(([market, domain]) => [domain, market === 'GB' ? 'UK' : market]));

export function targetsFromSources(sources, ownAsins = []) {
  const own = new Set(ownAsins.map(asin => asin.toUpperCase()));
  const targets = new Map();
  for (const source of sources) {
    const raw = source.raw;
    const market = raw?.Marketplace?.trim().toUpperCase();
    if (!domains[market]) throw new Error(`来源 ${source.source_id} 的站点缺失或不支持：${market || '(空)'}`);
    const product = productUrl(raw.ASIN?.trim() || '', domains[market]);
    const key = `${markets[new URL(product.url).hostname]}:${product.asin}`;
    if (!targets.has(key)) targets.set(key, {
      key, asin: product.asin, marketplace: key.split(':')[0], url: product.url,
      role: own.has(product.asin) ? 'own' : 'competitor', source_ids: []
    });
    if (source.source_id && !targets.get(key).source_ids.includes(source.source_id)) targets.get(key).source_ids.push(source.source_id);
  }
  return [...targets.values()];
}

export async function captureBatch(targets, { out, resume = false, headed = false, runCapture = capture, onProgress = () => {} }) {
  out = resolve(out);
  let previous = [];
  if (resume) {
    previous = JSON.parse(await readFile(resolve(out, 'index.json'), 'utf8')).products;
  } else {
    await mkdir(dirname(out), {recursive: true});
    await mkdir(out); // An existing batch is resumed explicitly, never overwritten by accident.
  }
  const products = targets.map(target => {
    const old = previous.find(item => item.key === target.key && item.url === target.url);
    return { ...target, status: 'pending', ...(old || {}), role: target.role, source_ids: target.source_ids };
  });
  const indexPath = resolve(out, 'index.json');
  const save = async () => {
    const summary = {
      total: products.length,
      captured: products.filter(p => p.status === 'captured').length,
      partial: products.filter(p => p.status === 'partial').length,
      failed: products.filter(p => p.status === 'failed').length,
      pending: products.filter(p => p.status === 'pending').length
    };
    await writeFile(indexPath, JSON.stringify({ updated_at: new Date().toISOString(), summary, products }, null, 2));
    return summary;
  };
  await save();
  for (const product of products) {
    if (resume && product.status === 'captured') {
      try {
        const snapshot = JSON.parse(await readFile(product.product_json, 'utf8'));
        if (snapshot.status === 'captured' && snapshot.requested_asin === product.asin &&
            productUrl(snapshot.source_url).url === product.url) {
          onProgress(`跳过已有结果 ${product.key}`);
          continue;
        }
      } catch { /* Missing/incomplete local snapshot is fetched again. */ }
    }
    onProgress(`采集 ${product.key} (${product.role})`);
    try {
      const result = await runCapture(product.url, {out: resolve(out, 'products'), headed});
      Object.assign(product, {status: result.status, title: result.title, product_json: resolve(result.folder, 'product.json'),
        missing_sections: result.missing_sections, captured_at: new Date().toISOString()});
      delete product.error;
      delete product.error_folder;
    } catch (error) {
      Object.assign(product, {status: 'failed', error: error.message, error_folder: error.folder || null});
      delete product.product_json;
      onProgress(`失败 ${product.key}：${error.message}`);
    }
    await save();
  }
  return {index: indexPath, summary: await save()};
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const args = process.argv.slice(2);
    const option = name => args.includes(name) ? args[args.indexOf(name) + 1] : undefined;
    const sourceFile = option('--sources');
    if (!sourceFile) throw new Error('用法：npm run capture:batch -- --sources 清洗结果/sources.json --own B0BW8JZ279 [--out 目录] [--resume]');
    const targets = targetsFromSources(JSON.parse(await readFile(sourceFile, 'utf8')), (option('--own') || '').split(',').filter(Boolean));
    if (!targets.length) throw new Error('来源文件没有商品');
    if (args.includes('--resume') && !option('--out')) throw new Error('--resume 需要 --out 指定已有批次目录');
    const result = await captureBatch(targets, {
      out: option('--out') || `output/batches/${new Date().toISOString().replaceAll(':', '-')}`,
      resume: args.includes('--resume'), headed: args.includes('--headed'), onProgress: console.error
    });
    console.log(JSON.stringify(result, null, 2));
    if (result.summary.failed || result.summary.partial) process.exitCode = 1;
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
