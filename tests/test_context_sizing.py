"""Synthetic planning checks only; no model inference."""
import copy
import json
import hashlib
from pathlib import Path
import unittest
from workbench.inventory import automatic_context

ROOT=Path(__file__).resolve().parents[1]
META={'model.context_length':262144}

def fixture(prompt='Return READY.',review=False):
    return {'instructions':'Follow the request.','source':{'initial_state':{'ignored':'data'}},
            'variants':[{'id':'v','prompt_style':'direct_text_v1','retry_enabled':review,
                         'steps':[{'type':'generate','prompt':prompt}]}]}

class ContextSizingTests(unittest.TestCase):
    def test_frozen_small_240_suite_is_16k_with_and_without_review(self):
        # Exact pre-large-suite definitions, archived from commit5151504e.
        snapshot=ROOT/'archives/suite-before-large-states-5151504e'
        pins=json.loads((snapshot/'SHA256.json').read_text(encoding='utf-8'))
        raw=(snapshot/'evaluation/catalog.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),pins['evaluation/catalog.json'])
        entries=[e for e in json.loads(raw)['definitions'] if e['scope']=='active']
        self.assertEqual(len(entries),1440)
        archive=ROOT/'archives/template-builds/19025a0440b84189'
        tests=[]
        for entry in entries:
            raw=(archive/entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest(),entry['source_sha256'])
            tests.append(json.loads(raw))
        before=copy.deepcopy(tests)
        on=automatic_context(tests,META)
        off=copy.deepcopy(tests)
        for t in off:
            for v in t['variants']:v['retry_enabled']=False
        normal=automatic_context(off,META)
        self.assertEqual(on['allocated_tokens'],16384)
        self.assertEqual(normal['allocated_tokens'],16384)
        self.assertEqual(on['input_estimate_bytes'],normal['input_estimate_bytes'])
        self.assertLess(on['review_control_estimate_bytes'],1536)
        self.assertEqual(tests,before)
        self.assertIsNone(on['output_cap'])
        self.assertEqual(on['capacity_policy'],'fixed-case-local-v1')

    def test_current_suite_estimates_transmitted_bytes_without_claiming_native_fit(self):
        tests=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'test_specs').glob('*.json')]
        before=copy.deepcopy(tests)
        on=automatic_context(tests,META)
        off=copy.deepcopy(tests)
        for test in off:
            for variant in test['variants']:variant['retry_enabled']=False
        normal=automatic_context(off,META)
        expected=max(len(test['instructions'].encode('utf-8'))+256+
                     sum(len(step['prompt'].encode('utf-8'))+128 for step in variant['steps'])
                     for test in tests for variant in test['variants'] if variant.get('enabled',True))
        self.assertEqual(on['input_estimate_bytes'],expected)
        self.assertEqual(normal['input_estimate_bytes'],expected)
        self.assertGreaterEqual(on['allocated_tokens'],normal['allocated_tokens'])
        self.assertLessEqual(on['allocated_tokens']-normal['allocated_tokens'],2048)
        self.assertLess(on['review_control_estimate_bytes'],1536)
        self.assertIsNone(on['output_cap'])
        self.assertIn('UTF-8 byte estimate',on['method'])
        self.assertEqual(tests,before)
        # Selected common C and actual-tokenizer fit are tested by study_protocol,
        # not inferred from this conservative automatic byte estimate.

    def test_direct_prompt_does_not_double_count_source_or_unused_prefix(self):
        t=fixture();first=automatic_context([t],META)
        t['source']={'initial_state':{'large':'unused '*50000}}
        t['shared_prefix']='unused '*50000
        self.assertEqual(first,automatic_context([t],META))
        t['variants'][0]['steps'][0]['prompt']+=' transmitted '*5000
        self.assertGreater(automatic_context([t],META)['allocated_tokens'],first['allocated_tokens'])

    def test_review_adds_only_fixed_controls_no_scaling(self):
        for n in (10,10000,11000,11500,11800,14000,27000,28000,29000,40000,60000,100000):
            t=fixture('x'*n);off=automatic_context([t],META)
            t['variants'][0]['retry_enabled']=True;on=automatic_context([t],META)
            self.assertEqual(off['input_estimate_bytes'],on['input_estimate_bytes'])
            self.assertGreaterEqual(on['allocated_tokens'],off['allocated_tokens'])
            self.assertLessEqual(on['allocated_tokens']-off['allocated_tokens'],2048)
            self.assertLess(on['review_control_estimate_bytes'],1536)
            self.assertIsNone(on['output_cap'])

    def test_review_near_power_of_two_boundary_adds_only_small_blocks(self):
        t=fixture('x'*11000)
        off=automatic_context([t],META)
        t['variants'][0]['retry_enabled']=True
        on=automatic_context([t],META)
        self.assertEqual(off['allocated_tokens'],16384)
        self.assertEqual(on['allocated_tokens'],17408)
        self.assertLessEqual(on['allocated_tokens']-off['allocated_tokens'],2048)
        self.assertEqual(on['allocated_tokens']%1024,0)
        self.assertIsNone(on['output_cap'])

    def test_native_bound_and_bytes_are_not_tokenizer_claims(self):
        t=fixture('雪'*10000,True)
        c=automatic_context([t],{'model.context_length':4096})
        self.assertEqual(c['allocated_tokens'],4096)
        self.assertTrue(c['input_may_exceed_native_context'])
        self.assertGreater(c['input_estimate_bytes'],30000)
        self.assertIn('byte estimate',c['method'])

    def test_disabled_review_variant_does_not_inflate_plan(self):
        t=fixture();off=automatic_context([t],META)
        t['variants'].append({**copy.deepcopy(t['variants'][0]),'id':'disabled','enabled':False,'retry_enabled':True})
        self.assertEqual(off,automatic_context([t],META))
