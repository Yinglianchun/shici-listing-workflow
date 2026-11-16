import copy
import tempfile
import unittest
from pathlib import Path
from judge import judge_pairs, validate_results,derive_coverage


def answer(identifier, relation='equivalent'):
    return {'id':identifier,'relation':relation,'left_covers_right':relation=='equivalent',
            'right_covers_left':relation=='equivalent','can_share_answer':True,
            'shared_intent':'紫外线防护','left_unique':[],'right_unique':[],'left_evidence':[],'right_evidence':[],
            'topics':['紫外线防护'],'reason':'仅改变表达方式，无新增条件'}


def inputs():
    groups=[{'group_id':'L','kind':'ai_generated_question','marketplace':'US','text':'Does it block UV?'},
            {'group_id':'R','kind':'ai_generated_question','marketplace':'US','text':'Does it protect against UV rays?'}]
    pairs=[{'left':'L','right':'R','left_text':groups[0]['text'],'right_text':groups[1]['text'],'score':.95}]
    return groups,pairs


class JudgeTests(unittest.TestCase):
    def test_coverage_computed_from_difference_lists_preserves_model_output(self):
        row=answer('0','partial_overlap')
        row.update({'left_unique':['高尔夫场景'],'left_evidence':['golf'],
                    'left_covers_right':False,'right_covers_left':True})
        result=derive_coverage(row)
        self.assertTrue(result['left_covers_right'])
        self.assertFalse(result['right_covers_left'])
        self.assertEqual(result['reported_coverage'],{'left_covers_right':False,'right_covers_left':True})
        self.assertFalse(row['left_covers_right'])
        self.assertEqual(derive_coverage(result),result)
        row['right_unique']=['徒步场景']
        result=derive_coverage(row)
        self.assertFalse(result['left_covers_right'])
        self.assertFalse(result['right_covers_left'])

    def test_observed_containment_relation_normalized_without_losing_report(self):
        row=answer('0','right_covers_left')
        row.update({'right_unique':['高尔夫场景'],'right_evidence':['golf']})
        result=derive_coverage(row)
        self.assertEqual(result['relation'],'partial_overlap')
        self.assertEqual(result['reported_relation'],'right_covers_left')
        self.assertTrue(result['right_covers_left'])
        self.assertFalse(result['left_covers_right'])

    def test_unknown_ids_and_inconsistent_equivalence_rejected(self):
        item={'id':'0','left':'UV400','right':'UV protection'}
        with self.assertRaises(ValueError):
            validate_results({'results':[answer('other')]},[item])
        invalid=answer('0')
        invalid['left_unique']=['只有左侧问小脸']
        with self.assertRaises(ValueError):
            validate_results({'results':[invalid]},[item])

    def test_one_original_span_can_support_multiple_unique_details(self):
        item={'id':'0','left':'yellow polarized lenses','right':'lenses'}
        result=answer('0','partial_overlap')
        result.update(left_unique=['黄色','偏光'],left_evidence=['yellow polarized'],left_covers_right=True,right_covers_left=False)
        checked=validate_results({'results':[result]},[item])
        self.assertEqual(len(checked['0']['left_unique']),2)
        result['left_evidence']=[]
        with self.assertRaises(ValueError):
            validate_results({'results':[result]},[item])
        invalid=answer('0','partial_overlap')
        invalid['left_unique']=['UV400规格']
        invalid['left_evidence']=['UV400']
        invalid['right_covers_left']=True
        with self.assertRaises(ValueError):
            validate_results({'results':[invalid]},[item])
        invalid=answer('0','partial_overlap')
        invalid['left_unique']=['男女通用']
        invalid['left_evidence']=['for men and women']
        with self.assertRaises(ValueError):
            validate_results({'results':[invalid]},[item])
        invalid=answer('0','same_topic')
        invalid['left_covers_right']=invalid['right_covers_left']=True
        with self.assertRaises(ValueError):
            validate_results({'results':[invalid]},[item])

    def test_cache_reuses_text_not_ephemeral_group_ids_and_retains_review_status(self):
        groups,pairs=inputs()
        before=copy.deepcopy(pairs)
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache.db'
            def request(items,*args):
                return {'results':[answer(i['id']) for i in items]}, {'total_tokens':11}
            result,stats=judge_pairs(pairs,groups,cache,transport=request,key_reader=lambda:'test-only')
            self.assertEqual(stats['total_tokens'],11)
            self.assertEqual(result[0]['status'],'needs_review')
            self.assertEqual(pairs,before)
            groups[0]['group_id']='newL'
            pairs[0]['left']='newL'
            def no_request(*args):
                self.fail('Cache hit must not call API or read credentials')
            result,stats=judge_pairs(pairs,groups,cache,transport=no_request,key_reader=no_request)
            self.assertEqual(stats['cache_hits'],1)
            self.assertEqual(result[0]['left'],'newL')

    def test_failed_pair_stays_unjudged_and_can_be_retried(self):
        groups,pairs=inputs()
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache.db'
            def fail(*args):
                raise RuntimeError('network test failure')
            result,stats=judge_pairs(pairs,groups,cache,transport=fail,key_reader=lambda:'test-only')
            self.assertEqual(result[0]['relation'],'unjudged')
            self.assertEqual(stats['failed_pairs'],1)
            def good(items,*args):
                return {'results':[answer(i['id'],'same_topic') for i in items]},{}
            result,stats=judge_pairs(pairs,groups,cache,transport=good,key_reader=lambda:'test-only')
            self.assertEqual(stats['cache_hits'],0)
            self.assertEqual(result[0]['relation'],'same_topic')

    def test_model_separation_and_cross_market_rejection(self):
        groups,pairs=inputs()
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache.db'
            calls=[]
            def request(items,model,*args):
                calls.append(model)
                return {'results':[answer(i['id']) for i in items]},{}
            for model in ['first','second']:
                judge_pairs(pairs,groups,cache,model=model,transport=request,key_reader=lambda:'test-only')
            self.assertEqual(calls,['first','second'])
            groups[1]['marketplace']='DE'
            with self.assertRaises(ValueError):
                judge_pairs(pairs,groups,cache,transport=request,key_reader=lambda:'test-only')

    def test_model_format_does_not_trigger_retry(self):
        groups,pairs=inputs()
        groups.extend([{'group_id':'L2','text':'Are lenses UV400?','kind':'ai_generated_question','marketplace':'US'},
                       {'group_id':'R2','text':'Do lenses offer UV400?','kind':'ai_generated_question','marketplace':'US'}])
        pairs.append({'left':'L2','right':'R2','left_text':'Are lenses UV400?','right_text':'Do lenses offer UV400?','score':.9})
        calls=[]
        def request(items,*args):
            calls.append([item['id'] for item in items])
            rows=[answer(item['id']) for item in items]
            if len(calls)==1:
                rows[1]['left_unique']=['不存在的信息']
                rows[1]['left_evidence']=['not in source']
            return {'results':rows},{'total_tokens':5}
        with tempfile.TemporaryDirectory() as directory:
            result,stats=judge_pairs(pairs,groups,Path(directory)/'cache.db',transport=request,key_reader=lambda:'test-only')
        self.assertEqual(calls,[['0','1']])
        self.assertEqual(stats['failed_pairs'],0)
        self.assertEqual(stats['total_tokens'],5)
        self.assertEqual(len(result),2)


if __name__=='__main__':
    unittest.main()
