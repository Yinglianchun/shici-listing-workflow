"""SiliconFlow embeddings and review-only semantic candidate retrieval."""
import json
import math
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections import defaultdict
from contextlib import closing
from pathlib import Path

ENDPOINT = 'https://api.siliconflow.cn/v1/embeddings'
DEFAULT_MODEL = 'BAAI/bge-m3'


def read_api_key():
    names = ('SILICONFLOW_API_KEY', 'siliconflow')
    for name in names:
        value = os.environ.get(name, '').strip()
        if value:
            return value
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
            for name in names:
                try:
                    value, _ = winreg.QueryValueEx(registry, name)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                except FileNotFoundError:
                    pass
    raise RuntimeError('未找到硅基流动密钥：请设置用户变量 siliconflow 或 SILICONFLOW_API_KEY')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_embeddings(texts, model, key):
    request = urllib.request.Request(ENDPOINT,
        data=json.dumps({'model': model, 'input': texts, 'encoding_format': 'float'}).encode('utf-8'),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(NoRedirect)
    for attempt in range(3):
        try:
            with opener.open(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            if code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            # Do not echo server bodies, request headers or credentials in errors.
            raise RuntimeError(f'硅基流动 embedding 请求失败：HTTP {code}') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError('硅基流动 embedding 网络连接失败；已完成批次可从缓存复用') from None
        except (ValueError, UnicodeError):
            raise RuntimeError('硅基流动返回的 embedding 不是有效 JSON') from None


def validate_vector(vector):
    if not isinstance(vector, list) or not vector or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector
    ):
        raise ValueError('Embedding 向量为空或包含无效数值')
    norm = math.sqrt(sum(x*x for x in vector))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError('Embedding 向量长度无效')
    return vector


def embed_texts(texts, cache_path, model=DEFAULT_MODEL, batch_size=32,
                transport=request_embeddings, key_reader=read_api_key, progress=lambda message: None):
    if not 1 <= batch_size <= 64:
        raise ValueError('Embedding 批大小必须在 1 到 64 之间')
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError('Embedding 输入不能是空文本')
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    vectors = {}
    unique = list(dict.fromkeys(texts))
    stats = {'provider': 'siliconflow', 'model': model, 'unique_texts': len(unique),
             'cache_hits': 0, 'requested_texts': 0, 'requests': 0, 'total_tokens': 0}
    with closing(sqlite3.connect(cache_path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS embeddings (model TEXT NOT NULL, text TEXT NOT NULL, vector TEXT NOT NULL, PRIMARY KEY(model,text))')
        for text in unique:
            row = db.execute('SELECT vector FROM embeddings WHERE model=? AND text=?', (model, text)).fetchone()
            if row:
                vectors[text] = validate_vector(json.loads(row[0]))
        stats['cache_hits'] = len(vectors)
        missing = [text for text in unique if text not in vectors]
        key = key_reader() if missing else None
        for offset in range(0, len(missing), batch_size):
            batch = missing[offset:offset+batch_size]
            response = transport(batch, model, key)
            data = response.get('data', [])
            if (len(data) != len(batch) or any(type(item.get('index')) is not int for item in data)
                    or sorted(item['index'] for item in data) != list(range(len(batch)))):
                raise ValueError('Embedding 返回数量或索引不符，当前批次未写入缓存')
            ordered = sorted(data, key=lambda item: item['index'])
            batch_vectors = [validate_vector(item.get('embedding')) for item in ordered]
            dimensions = {len(v) for v in vectors.values()} | {len(v) for v in batch_vectors}
            if len(dimensions) != 1:
                raise ValueError('同一模型返回的向量维度不一致，当前批次未写入缓存')
            for text, vector in zip(batch, batch_vectors):
                db.execute('INSERT OR REPLACE INTO embeddings VALUES (?,?,?)', (model, text, json.dumps(vector)))
                vectors[text] = vector
            db.commit()
            stats['requested_texts'] += len(batch)
            stats['requests'] += 1
            stats['total_tokens'] += response.get('usage', {}).get('total_tokens', 0)
            progress(f'Embedding {offset+len(batch)}/{len(missing)}；缓存命中 {stats["cache_hits"]}')
    dimensions = {len(v) for v in vectors.values()}
    if len(dimensions) > 1:
        raise ValueError('缓存中的向量维度不一致，请更换缓存文件后重试')
    stats['dimensions'] = next(iter(dimensions), 0)
    return [vectors[text] for text in texts], stats


def difference_hints(left, right):
    """Expose details for review, without inferring equivalence or product truth."""
    patterns = {
        '数字/单位': r'\b\d+(?:\.\d+)?\s*(?:mm|cm|inches|inch|g|oz|seconds?|minutes?)?\b',
        '否定表达': r'\b(?:not|no|non[- ]?polarized|without|never|cannot)\b|n\x27t\b',
        '适配/使用条件': r'\b(?:small|medium|large|narrow|wide|night|daytime|day|indoor|outdoor|indoors|outdoors|prescription|children|adults|men|women)\b'
    }
    hints = []
    for label, pattern in patterns.items():
        a = set(re.findall(pattern, left.casefold()))
        b = set(re.findall(pattern, right.casefold()))
        if a != b:
            hints.append(f'{label}：左[{", ".join(sorted(a))}] / 右[{", ".join(sorted(b))}]')
    return hints


def semantic_candidates(groups, vectors, threshold=.75, top_k=5, use_numpy=True):
    if len(groups) != len(vectors):
        raise ValueError('文本组与向量数量不符')
    if not 0 <= threshold <= 1 or top_k < 1:
        raise ValueError('相似度需在 0 到 1 之间，top_k 必须大于 0')
    vectors = [validate_vector(v) for v in vectors]
    if len({len(v) for v in vectors}) > 1:
        raise ValueError('向量维度不一致')
    normalized = []
    for vector in vectors:
        norm = math.sqrt(sum(x*x for x in vector))
        normalized.append([x/norm for x in vector])
    buckets = defaultdict(list)
    for i, group in enumerate(groups):
        buckets[(group['marketplace'], group['kind'])].append(i)
    try:
        if not use_numpy:
            raise ImportError
        import numpy as np
    except ImportError:
        np = None
    pairs = {}
    without_neighbor = []
    for indices in buckets.values():
        matrix = np.asarray([normalized[i] for i in indices]) if np is not None else None
        for local, i in enumerate(indices):
            if np is not None:
                scores = matrix @ matrix[local]
                neighbors = [(float(scores[j]), other) for j, other in enumerate(indices) if other != i and scores[j] >= threshold]
            else:
                neighbors = []
                for j in indices:
                    if i != j:
                        score = sum(a*b for a, b in zip(normalized[i], normalized[j]))
                        if score >= threshold:
                            neighbors.append((score, j))
            neighbors.sort(key=lambda item: (-item[0], item[1]))
            if not neighbors:
                without_neighbor.append(groups[i]['group_id'])
            for score, j in neighbors[:top_k]:
                a, b = sorted((i, j))
                pairs[(a, b)] = max(-1., min(1., score))
    result = []
    for (a, b), score in pairs.items():
        left, right = groups[a], groups[b]
        stop = set('do does are is these this the a an for with to of it and how what can'.split())
        left_tokens = set(re.findall(r"[\w'-]+", left['normalized'])) - stop
        right_tokens = set(re.findall(r"[\w'-]+", right['normalized'])) - stop
        union = left_tokens | right_tokens
        result.append({'left': left['group_id'], 'right': right['group_id'],
                       'left_text': left['text'], 'right_text': right['text'],
                       'score': round(score, 6), 'score_type': 'embedding_cosine',
                       'token_overlap': round(len(left_tokens & right_tokens)/len(union), 6) if union else 0.,
                       'left_only_tokens': sorted(left_tokens-right_tokens), 'right_only_tokens': sorted(right_tokens-left_tokens),
                       'condition_hints': difference_hints(left['text'], right['text']),
                       'relation': 'unjudged', 'status': 'needs_review',
                       'reason': '语义相近候选；尚未判断是否同义、部分重合或仅同主题'})
    result.sort(key=lambda item: (-item['score'], item['left'], item['right']))
    return result, {'threshold': threshold, 'top_k_per_group': top_k, 'candidate_pairs': len(result),
                    'groups_without_neighbor': without_neighbor, 'similarity_backend': 'numpy' if np is not None else 'python'}
