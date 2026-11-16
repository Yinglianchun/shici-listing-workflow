import json
import tempfile
import unittest
from pathlib import Path
from semantic import embed_texts, semantic_candidates, difference_hints


class SemanticTests(unittest.TestCase):
    def test_response_order_and_cache_avoid_repeated_requests_and_key_reads(self):
        calls = []
        def request(texts, model, key):
            calls.append(texts)
            return {'data': [{'index': i, 'embedding': [i+1, 1.]} for i in reversed(range(len(texts)))],
                    'usage': {'total_tokens': 7}}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache.db'
            vectors, stats = embed_texts(['one', 'two', 'one'], cache, transport=request, key_reader=lambda:'test-only')
            self.assertEqual(vectors, [[1, 1.], [2, 1.], [1, 1.]])
            self.assertEqual(stats['requested_texts'], 2)
            def no_key():
                self.fail('Cached run must not read credentials')
            again, stats = embed_texts(['two', 'one'], cache, transport=request, key_reader=no_key)
            self.assertEqual(again, [[2,1.], [1,1.]])
            self.assertEqual(stats['cache_hits'],2)
            self.assertEqual(len(calls),1)

    def test_invalid_indices_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)/'cache.db'
            bad = lambda *args: {'data':[{'index':0,'embedding':[1,2]}, {'index':0,'embedding':[2,3]}]}
            with self.assertRaises(ValueError):
                embed_texts(['a','b'],cache,transport=bad,key_reader=lambda:'test-only')
            calls=[]
            def good(texts, *args):
                calls.extend(texts)
                return {'data':[{'index':i,'embedding':[1,2]} for i in range(len(texts))]}
            embed_texts(['a','b'],cache,transport=good,key_reader=lambda:'test-only')
            self.assertEqual(calls,['a','b'])

    def test_interrupted_batch_reuses_completed_texts(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)/'cache.db'
            def fail_second(texts,*args):
                if texts == ['b']:
                    raise RuntimeError('test interruption')
                return {'data':[{'index':0,'embedding':[1,2]}]}
            with self.assertRaises(RuntimeError):
                embed_texts(['a','b'],cache,batch_size=1,transport=fail_second,key_reader=lambda:'test-only')
            calls=[]
            def good(texts,*args):
                calls.extend(texts)
                return {'data':[{'index':0,'embedding':[2,1]}]}
            _,stats = embed_texts(['a','b'],cache,batch_size=1,transport=good,key_reader=lambda:'test-only')
            self.assertEqual(calls,['b'])
            self.assertEqual(stats['cache_hits'],1)

    def test_retrieval_keeps_conditions_and_does_not_cross_kinds_or_markets(self):
        texts=['Do these fit small faces?', 'Are these suitable for large faces?', 'small faces', 'small faces']
        groups=[{'group_id':str(i),'text':t,'normalized':t.lower(),'marketplace':'DE' if i==3 else 'US',
                 'kind':'keyword' if i==2 else 'ai_generated_question'} for i,t in enumerate(texts)]
        for backend in (False, True):
            candidates,stats=semantic_candidates(groups,[[1,0],[1,0],[1,0],[1,0]],.5,1,use_numpy=backend)
            self.assertEqual(len(candidates),1)
            self.assertEqual(candidates[0]['status'],'needs_review')
            self.assertEqual(candidates[0]['relation'],'unjudged')
            self.assertTrue(candidates[0]['condition_hints'])
            self.assertEqual(stats['groups_without_neighbor'],['2','3'])

    def test_dimensions_and_invalid_vectors_rejected(self):
        groups=[{'group_id':str(i),'text':'text','normalized':'text','marketplace':'US','kind':'keyword'} for i in range(2)]
        for vectors in ([[1,2],[1]], [[0,0],[1,2]], [[float('nan'),1],[1,2]]):
            with self.assertRaises(ValueError):
                semantic_candidates(groups,vectors)
        hints=difference_hints('14 cm non-polarized small face','14 mm polarized large face')
        self.assertEqual(len(hints),3)


if __name__=='__main__':
    unittest.main()
