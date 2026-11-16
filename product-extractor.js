(function extractProduct() {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const text = selector => clean(document.querySelector(selector)?.innerText);
  const content = el => {
    if (!el) return '';
    const copy = el.cloneNode(true);
    copy.querySelectorAll('script,style,noscript,template').forEach(node => node.remove());
    return clean(copy.textContent);
  };
  const pairs = selector => [...new Map([...document.querySelectorAll(selector)].map(row => {
    const cells = [...row.querySelectorAll('th,td')].map(content);
    return cells.length >= 2 ? { name: cells[0], value: cells.slice(1).join(' ') } : null;
  }).filter(Boolean).map(pair => [JSON.stringify([pair.name,pair.value]),pair])).values()];
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
    specifications: pairs('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, .product-facts-detail tr, table.voyager-ns-desktop-table tr, table.prodDetTable tr, #style tr, #features_and_specs tr'),
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
})()
