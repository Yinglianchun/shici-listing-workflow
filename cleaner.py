"""CSV import, conservative deduplication, question phrase extraction and review candidates."""
import argparse
import csv
import difflib
import json
import re
import time
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def normalize(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = text.translate(str.maketrans({'’': "'", '‘': "'", '–': '-', '—': '-'}))
    return re.sub(r'\s+', ' ', text).strip().rstrip('?.!').strip()


def phrase(text):
    """Extract a key-expression draft at any length; retain meaningful relationships."""
    text = normalize(text)
    # Expand negation before removing auxiliaries (can't must not become 't).
    text = re.sub(r"\bcan't\b", 'can not', text)
    text = re.sub(r"\bwon't\b", 'will not', text)
    text = re.sub(r"\b([a-z]+)n't\b", r'\1 not', text)
    if re.match(r'^how long\b', text) and 'darken' in text:
        text = re.sub(r'^how long\s+(?:do|does)\s+', '', text)
        text = re.sub(r'\s+take to darken\b', ' darkening time', text)
    elif re.match(r'^how long\b', text):
        return {'text': text, 'needs_review': True, 'reason': '时间意图需改写，保留原表达'}
    elif re.match(r'^how (?:dark|wide|heavy|fast|much|many)\b', text):
        return {'text': text, 'needs_review': True, 'reason': '程度或数量意图需改写，保留原表达'}
    else:
        text = re.sub(r'^(?:what is|what are|how should|how can|how do|how does|do|does|are|is|can|will)\s+', '', text)
    # Remove question scaffolding, not every preposition: "for hiking", "with a
    # case", "without slipping", "under 30 g" and "fit over" carry meaning.
    text = re.sub(r'\b(?:what|how|do|does|did|is|are|was|were|be|been|can|could|would|should|will|may|might|have|has|had|these|those|this|that|they|them|their|it|its|i|my|me|you|your|we|our|a|an|the)\b', ' ', text)
    text = re.sub(r'\b(?:good|suitable|designed|intended)\s+for\b', 'for', text)
    text = re.sub(r'\b(?:come|comes)\s+with\b', 'with', text)
    text = re.sub(r'[?？]', ' ', text)
    # Negation, dimensions, use cases and comparative conditions stay intact.
    return {'text': re.sub(r'\s+', ' ', text).strip(), 'needs_review': True, 'reason': '短语候选；未核实商品适用性'}


def load(paths):
    records = []
    for path in sorted({p.resolve() for p in paths}):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            required = {'Keyword', 'Type', 'ASIN'}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f'{path.name} 缺少列：{required - set(reader.fieldnames or [])}')
            for row_number, row in enumerate(reader, 2):
                if None in row or any(row.get(k) is None for k in required):
                    raise ValueError(f'{path.name} 第 {row_number} 条记录列数异常')
                if not row['Keyword'].strip():
                    raise ValueError(f'{path.name} 第 {row_number} 条记录文本为空')
                kind = {'关键词': 'keyword', '买家问句': 'ai_generated_question'}.get(row['Type'].strip(), 'unknown')
                records.append({'source_id': f'S{len(records)+1:06}', 'file': str(path),
                                'csv_record': row_number, 'kind': kind, 'raw': row})
    return records


def deduplicate(records):
    groups = {}
    for record in records:
        raw = record['raw']
        # Marketplace and content kind do not silently collapse together.
        key = (raw.get('Marketplace', '').strip().upper(), record['kind'], raw['Type'].strip(), normalize(raw['Keyword']))
        if key not in groups:
            groups[key] = {'group_id': f'G{len(groups)+1:06}', 'kind': record['kind'],
                           'marketplace': key[0], 'text': raw['Keyword'], 'normalized': key[3],
                           'sources': [], 'asins': [], 'variants': []}
        group = groups[key]
        group['sources'].append(record['source_id'])
        asin = raw['ASIN'].strip().upper()
        if asin and asin not in group['asins']:
            group['asins'].append(asin)
        if raw['Keyword'] not in group['variants']:
            group['variants'].append(raw['Keyword'])
    for group in groups.values():
        group['duplicate_kind'] = 'normalized' if len(group['variants']) > 1 else 'exact' if len(group['sources']) > 1 else 'unique'
        if group['kind'] == 'ai_generated_question':
            group['phrase_candidate'] = phrase(group['text'])
    return list(groups.values())


def attach_products(records, index_path):
    """Link each source's own ASIN snapshot; never assign competitor facts to own product."""
    index = json.loads(index_path.read_text(encoding='utf-8'))
    products = {}
    for item in index['products']:
        key = (item['marketplace'], item['asin'])
        if key in products:
            raise ValueError(f'商品索引存在重复项：{key}')
        products[key] = item
    linked = 0
    for record in records:
        raw = record['raw']
        market = raw.get('Marketplace', '').strip().upper()
        market = 'UK' if market == 'GB' else market
        asin = raw['ASIN'].strip().upper()
        product = products.get((market, asin))
        reference = {'status': 'not_captured', 'asin': asin, 'marketplace': market}
        if product:
            reference.update({'status': product['status'], 'role': product['role']})
            if product['status'] in ('captured', 'partial'):
                path = Path(product['product_json'])
                snapshot = json.loads(path.read_text(encoding='utf-8'))
                if snapshot['requested_asin'] != asin or snapshot['status'] != product['status']:
                    raise ValueError(f'商品快照与索引不符：{path}')
                reference.update({'product_json': str(path.resolve()), 'source_type': 'listing_claim'})
                linked += 1
        record['product_detail'] = reference
    return linked


def similar_candidates(groups, threshold=.83, limit=500):
    # Word overlap narrows candidates; no similarity suggestion is auto-merged.
    index = defaultdict(set)
    result = []
    stop = set('do does are is these this the a an for with to of it and how what can sunglasses glasses'.split())
    for pos, group in enumerate(groups):
        tokens = set(re.findall(r"[\w'-]+", group['normalized'])) - stop
        bucket = (group['marketplace'], group['kind'])
        previous = set().union(*(index[(bucket, word)] for word in tokens)) if tokens else set()
        for other in sorted(previous):
            left = groups[other]
            score = difflib.SequenceMatcher(None, left['normalized'], group['normalized'], autojunk=False).ratio()
            if score >= threshold:
                result.append({'left': left['group_id'], 'right': group['group_id'], 'score': round(score, 4),
                               'left_text': left['text'], 'right_text': group['text'],
                               'status': 'needs_review', 'reason': '字面相近，不代表同一意图或同一商品事实'})
        for word in tokens:
            index[(bucket, word)].add(pos)
    result.sort(key=lambda item: (-item['score'], item['left'], item['right']))
    return result[:limit], len(result)


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def write_csv(path, columns, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows([[safe_cell(v) for v in row] for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--threshold', type=float, default=.83)
    parser.add_argument('--products', type=Path, help='批量采集的 index.json，将来源记录关联到对应商品详情')
    parser.add_argument('--similarity', choices=['lexical', 'siliconflow'], default='lexical')
    parser.add_argument('--embedding-model', default='BAAI/bge-m3')
    parser.add_argument('--embedding-cache', type=Path, default=Path('output/embedding-cache.sqlite3'))
    parser.add_argument('--embedding-batch-size', type=int, default=32)
    parser.add_argument('--semantic-threshold', type=float, default=.75)
    parser.add_argument('--neighbors', type=int, default=5, help='每条文本保留的相近候选数；对称合并后可能超过此数')
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error('--threshold 必须在 0 到 1 之间')
    if not 0 <= args.semantic_threshold <= 1 or args.neighbors < 1 or not 1 <= args.embedding_batch_size <= 64:
        parser.error('语义阈值需在 0 到 1 之间，neighbors 大于 0，embedding 批大小为 1 到 64')
    if args.out.exists():
        parser.error('输出目录已存在，请选择新目录')
    started = time.perf_counter()
    paths = []
    for source in args.inputs:
        paths.extend(source.glob('*.csv') if source.is_dir() else [source])
    if not paths:
        parser.error('没有找到 CSV')
    records = load(paths)
    linked = attach_products(records, args.products) if args.products else 0
    groups = deduplicate(records)
    semantic_meta = None
    if args.similarity == 'siliconflow':
        from semantic import embed_texts, semantic_candidates
        vectors, embedding_stats = embed_texts([g['text'] for g in groups], args.embedding_cache,
            model=args.embedding_model, batch_size=args.embedding_batch_size,
            progress=lambda message: print(message, file=sys.stderr))
        candidates, retrieval_stats = semantic_candidates(groups, vectors, args.semantic_threshold, args.neighbors)
        semantic_meta = {'embedding': embedding_stats, 'retrieval': retrieval_stats}
        total = len(candidates)
    else:
        candidates, total = similar_candidates(groups, args.threshold)
    # A fresh folder avoids overwriting reviewed results.
    args.out.mkdir(parents=True, exist_ok=False)
    summary = {'files': len({r['file'] for r in records}), 'source_records': len(records), 'unique_text_groups': len(groups),
               'duplicate_records': len(records)-len(groups), 'asins': len({r['raw']['ASIN'] for r in records}),
               'similar_candidates_total': total, 'similar_candidates_exported': len(candidates),
               'records_linked_to_product': linked,
               'similarity_method': args.similarity,
               'elapsed_seconds': round(time.perf_counter()-started, 3),
               'scope': '确定性重复归并；embedding 仅召回候选，未做 LLM 关系判断、自动语义合并、事实核验或重新分级。' if semantic_meta else '确定性重复归并；相近候选仅按字面相似度。未进行语义聚类、事实核验、重新分级。'}
    if semantic_meta:
        summary['embedding'] = semantic_meta['embedding']
        (args.out / 'semantic_metadata.json').write_text(json.dumps(semantic_meta, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, value in [('sources', records), ('groups', groups), ('similar_candidates', candidates), ('summary', summary)]:
        (args.out / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    for kind, name in [('keyword', '关键词去重'), ('ai_generated_question', '问句去重'), ('unknown', '未知类型')]:
        selected = [g for g in groups if g['kind'] == kind]
        write_csv(args.out / f'{name}.csv', ['组ID', '原文代表', '原始变体', '来源数', 'ASIN', '来源ID', '重复类型', '精简短语候选'],
                  [[g['group_id'], g['text'], ' | '.join(g['variants']), len(g['sources']), ','.join(g['asins']), ','.join(g['sources']), g['duplicate_kind'], g.get('phrase_candidate', {}).get('text', '')] for g in selected])
    if semantic_meta:
        write_csv(args.out / '语义相近项待复核.csv', ['左组', '右组', '左原文', '右原文', '语义相似度', '词项重合度', '左独有词', '右独有词', '条件差异提示', '关系判断', '状态'],
                  [[c['left'], c['right'], c['left_text'], c['right_text'], c['score'], c['token_overlap'],
                    ' | '.join(c['left_only_tokens']), ' | '.join(c['right_only_tokens']), '；'.join(c['condition_hints']), c['relation'], c['status']] for c in candidates])
    else:
        write_csv(args.out / '相近项待复核.csv', ['左组', '右组', '左原文', '右原文', '字面相似度', '状态'],
                  [[c['left'], c['right'], c['left_text'], c['right_text'], c['score'], c['status']] for c in candidates])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
