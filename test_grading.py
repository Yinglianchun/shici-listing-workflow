import tempfile
import unittest
from pathlib import Path
from grading import normalize_assessment,compute_level,analyse


def row(identifier,core,attributes):
    return {'id':identifier,'core_term':core,'attributes':attributes,'intent':'商品属性','intent_concept':'product_features',
            'intent_evidence':[],'topic':'尺寸与适配','unresolved':[],'needs_review':False,'review_reason':''}


def attribute(concept,value,evidence):
    return {'concept':concept,'value':value,'label':concept,'evidence':evidence}


class GradingTests(unittest.TestCase):
    def test_confirmed_womens_core_and_complete_frame_attributes(self):
        core="women's sunglasses"
        cases=[('',[],0),('full frame ',[attribute('frame_structure','full frame','full frame')],1),
               ('gold frame ',[attribute('frame_color','gold','gold frame')],1),
               ('gold full frame ',[attribute('frame_color','gold','gold'),attribute('frame_structure','full frame','full frame')],2)]
        for prefix,attrs,expected in cases:
            for spelling in (core,'women’s sunglasses','women sunglasses','womens sunglasses'):
                with self.subTest(text=prefix+spelling):
                    item={'id':'A','text':prefix+spelling,'kind':'keyword','core_candidates':[core]}
                    result=normalize_assessment(row('A',core,[*attrs,attribute('gender','women','women')]),item)
                    self.assertEqual(compute_level(result,'keyword')['level'],expected)
                    self.assertEqual(len(result['excluded_core_attributes']),1)

    def test_measurement_is_one_attribute_and_gender_outside_core_is_unchanged(self):
        item={'id':'A','text':'14cm arm length sunglasses','kind':'keyword','core_candidates':['sunglasses']}
        measured=normalize_assessment(row('A','sunglasses',[attribute('temple_length','14cm','14cm arm length')]),item)
        self.assertEqual(compute_level(measured,'keyword')['level'],1)
        item={'id':'B','text':'sunglasses for women','kind':'keyword','core_candidates':['sunglasses']}
        gender=normalize_assessment(row('B','sunglasses',[attribute('gender','women','for women')]),item)
        self.assertEqual(compute_level(gender,'keyword')['level'],1)

    def test_hyphen_spelling_in_source_and_evidence_does_not_hide_attributes(self):
        for phrase,concept in [('non-polarized','polarization'),('anti-glare','glare_reduction'),('non-slip','slip_resistance')]:
            item={'id':'A','text':phrase+' sunglasses','kind':'keyword','core_candidates':['sunglasses']}
            result=normalize_assessment(row('A','sunglasses',[attribute(concept,phrase,phrase.replace('-',' '))]),item)
            self.assertEqual(compute_level(result,'keyword')['level'],1)

    def test_face_shape_is_not_counted_again_as_frame_shape(self):
        item={'id':'A','text':'sunglasses for oval faces','kind':'keyword','core_candidates':['sunglasses']}
        result=normalize_assessment(row('A','sunglasses',[attribute('face_fit','oval faces','oval faces')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],1)
        self.assertNotIn('shape',[a['concept'] for a in result['attributes']])
        item['text']='oval sunglasses for round faces'
        result=normalize_assessment(row('A','sunglasses',[attribute('face_fit','round faces','round faces')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],2)

    def test_compound_measurement_and_fit_over_count_once_each(self):
        text='sunglasses with 14cm arm length that fit over prescription glasses'
        item={'id':'A','text':text,'core_candidates':['sunglasses']}
        result=normalize_assessment(row('A','sunglasses',[
            attribute('temple_length','14cm','14cm arm length'),attribute('fit_over','prescription glasses','fit over prescription glasses')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],2)

    def test_synonyms_deduplicated_but_lightweight_and_face_fit_separate(self):
        item={'id':'A','text':'UV400 UV protection lightweight sunglasses for small faces','core_candidates':['sunglasses']}
        result=normalize_assessment(row('A','sunglasses',[
            attribute('uv400','UV400','UV400'),attribute('uv_protection','UV protection','UV protection'),
            attribute('lightweight','lightweight','lightweight'),attribute('face_fit','small faces','small faces')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],3)
        self.assertEqual(len(result['attributes'][0]['values']),2)

    def test_attributes_already_inside_core_not_counted(self):
        item={'id':'A','text':'night driving glasses for men','core_candidates':['night driving glasses']}
        result=normalize_assessment(row('A','night driving glasses',[
            attribute('driving','night driving','night driving'),attribute('gender','men','men')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],1)
        self.assertEqual(len(result['excluded_core_attributes']),1)

    def test_helper_phrase_not_counted_and_core_case_preserved(self):
        item={'id':'A','text':'Do sunglasses help with glare?','core_candidates':['Sunglasses']}
        result=normalize_assessment(row('A','sunglasses',[
            attribute('help_with','help with','help with'),attribute('glare_reduction','glare','glare')]),item)
        self.assertEqual(result['core_term'],'Sunglasses')
        self.assertEqual(compute_level(result,'keyword')['level'],1)
        self.assertEqual(len(result['excluded_structure_attributes']),1)

    def test_missed_shape_recovered_and_other_omissions_remain_visible(self):
        item={'id':'A','text':'rectangular night driving glasses','kind':'keyword','core_candidates':['night driving glasses']}
        result=normalize_assessment(row('A','night driving glasses',[]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],1)
        self.assertEqual(result['attributes'][0]['concept'],'shape')
        item={'id':'B','text':'sunglasses titanium frame','kind':'keyword','core_candidates':['sunglasses']}
        result=normalize_assessment(row('B','sunglasses',[]),item)
        self.assertIn('titanium',result['unresolved'])
        self.assertIsNone(compute_level(result,'keyword')['level'])

    def test_generic_part_noun_not_a_material_and_activity_policy_can_be_changed(self):
        item={'id':'A','text':'night driving glasses comfortable frames','kind':'keyword','core_candidates':['night driving glasses']}
        result=normalize_assessment(row('A','night driving glasses',[
            attribute('comfort','comfortable','comfortable'),attribute('frame_material','frames','frames')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],1)
        item={'id':'B','text':'sunglasses for fishing and golf','kind':'keyword','core_candidates':['sunglasses']}
        result=normalize_assessment(row('B','sunglasses',[attribute('usage_scenario','fishing and golf','fishing and golf')]),item)
        self.assertEqual(compute_level(result,'keyword')['level'],2)
        self.assertIsNone(compute_level(result,'keyword',activity_policy='pending')['level'])
        self.assertEqual(compute_level(result,'keyword',activity_policy='per-value')['level'],2)
        self.assertEqual(compute_level(result,'keyword',activity_policy='per-concept')['level'],1)

    def test_confirmed_question_policy_and_no_double_counting_same_focus(self):
        clean=row('A','sunglasses',[]);clean.update(intent='清洁方法',intent_concept='cleaning')
        self.assertEqual(compute_level(clean,'ai_generated_question')['level'],0)
        self.assertIsNone(compute_level(clean,'ai_generated_question','pending')['level'])
        self.assertEqual(compute_level(clean,'ai_generated_question','attributes-only')['level'],0)
        self.assertEqual(compute_level(clean,'ai_generated_question','include-intent')['level'],1)
        polarized=row('B','sunglasses',[{'concept':'polarization'}]);polarized.update(intent='是否偏光',intent_concept='polarization')
        self.assertEqual(compute_level(polarized,'ai_generated_question','include-intent')['level'],1)

    def test_model_evidence_preserved_for_manual_review(self):
        item={'id':'A','text':'sunglasses for men','core_candidates':['sunglasses']}
        result=normalize_assessment(row('A','sunglasses',[attribute('gender','women','for women')]),item)
        self.assertEqual(result['raw_response']['attributes'][0]['evidence'],'for women')
        result=row('A','sunglasses',[]);result['unresolved']=['for men']
        self.assertIsNone(compute_level(result,'keyword')['level'])

    def test_incomplete_model_fields_do_not_trigger_retry_and_are_cached(self):
        item={'id':'A','text':'sunglasses','kind':'keyword','core_candidates':['sunglasses']}
        calls=[]
        raw={'id':'A','needs_review':'false','attributes':[{'concept':'size'}]}
        def request(*args):
            calls.append(1)
            return {'results':[raw]},{}
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache.db'
            result,stats=analyse([item],cache,transport=request,key_reader=lambda:'test')
            self.assertEqual(stats['failed_items'],0)
            self.assertEqual(result['A']['raw_response'],raw)
            result,stats=analyse([item],cache,transport=request,key_reader=lambda:self.fail('cached'))
            self.assertEqual(len(calls),1)
            self.assertEqual(stats['cache_hits'],1)

    def test_cache_reuse_without_credentials_and_model_ids_do_not_leak_into_output(self):
        item={'id':'A','text':'sunglasses','kind':'keyword','core_candidates':['sunglasses']}
        calls=[]
        def request(items,*args):
            calls.append(items)
            return {'results':[row(i['id'],'sunglasses',[]) for i in items]}, {'total_tokens':4}
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache.db'
            result,stats=analyse([item],cache,transport=request,key_reader=lambda:'test-only')
            self.assertEqual(stats['failed_items'],0)
            updated={**item,'id':'B'}
            def no_key():self.fail('Cache-only run must not read credentials')
            result,stats=analyse([updated],cache,transport=request,key_reader=no_key)
            self.assertEqual(stats['cache_hits'],1)
            self.assertEqual(result['B']['id'],'B')
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
