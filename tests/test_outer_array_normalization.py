"""Approved delimiter tolerance, with unchanged semantic and evidence gates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from normalization import normalize_outer_array
from evaluation.core import assess_record
from evaluation.__main__ import replay
from evaluation.validation import get_validator
from tests.test_versioned_validation import record
from workbench.domain import ResultStore, code_fingerprint

V = 'dot-outer-arrays-v1'


def spellings(text):
    return (text, text[1:], text[:-1], text[1:-1])


def response(raw, text):
    result = copy.deepcopy(raw)
    result['outputs']['patch'] = text
    result['calls'][0]['text'] = text
    return result


class OuterArrayNormalizationTests(unittest.TestCase):
    def test_opening_closing_both_whitespace_and_multiple_operations(self):
        ops = [{'op':'replace','path':'a','value':'  [brackets] \\ "quote"\n  '},
               {'op':'remove','path':'b'}]
        text = json.dumps(ops)
        for n, raw in enumerate(spellings(text)):
            with self.subTest(n=n):
                result = normalize_outer_array(' \t'+raw+'\r\n')
                self.assertEqual(result.operations, ops)
                self.assertEqual(json.loads(result.to_json()), ops)
                self.assertEqual((result.added_opening,result.added_closing),
                                 ((False,False),(True,False),(False,True),(True,True))[n])

    def test_valid_empty_array_only_is_accepted(self):
        self.assertEqual(normalize_outer_array(' [ ] ').operations, [])
        for raw in ('', ' ', '[', ']', '[ ', ' ]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                normalize_outer_array(raw)

    def test_malformed_internal_json_is_never_balanced_or_rewritten(self):
        bad = ['[{"value":"unfinished}', '[{"value":[1,2}', '[{},',
               '{"value":1e}', '{"value":01}', '{"x":1,"x":2}',
               '{"value":NaN}', '{"value":Infinity}', '[{}] trailing',
               'before [{}]', '```json\n[{}]\n```', '{};{}', '[{}][{}]',
               '[1', '[true', '[null', '[{} , ]', '{"value":"bad\\q"}',
               '{"value":"bad\\u00"}', '\ufeff{}', '{}\u00a0']
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                normalize_outer_array(raw)

    def test_nested_types_and_bracket_characters_are_preserved(self):
        value = {'text':'][{}\n\t\\"', 'nested':[True,False,None,1,'1',1.5,{}]}
        text = json.dumps([{'op':'replace','path':'field','value':value}],ensure_ascii=False)
        for raw in spellings(text):
            self.assertEqual(normalize_outer_array(raw).operations[0]['value'], value)

    def test_non_text_and_decoder_recursion_errors_fail_closed(self):
        from unittest.mock import patch
        for raw in (None, [], 1):
            with self.subTest(kind=type(raw).__name__), self.assertRaises(ValueError):
                normalize_outer_array(raw)
        # The Python JSON implementation's nesting capacity is runtime-specific.
        # Verify its actual error contract, not an assumed 1,500-level threshold.
        with patch('normalization.outer_arrays._strict',side_effect=RecursionError('decoder depth')):
            with self.assertRaises(ValueError):normalize_outer_array('[{"x":0}]')

    def test_each_bracket_variant_passes_only_under_new_version(self):
        r = record();before = copy.deepcopy(r)
        for i,text in enumerate(spellings(r['outputs']['patch'])):
            assessment = assess_record(response(r,text),validator=V)
            self.assertEqual(assessment['objective_outcome'],'PASS')
            self.assertEqual(any(c['code']=='json.outer_array_normalization'for c in assessment['checks']),i>0)
            if i:
                self.assertEqual(assess_record(response(r,text),validator='dot-separators-v2')['objective_outcome'],'FAIL')
        self.assertEqual(r,before)

    def test_wrong_values_paths_extra_writes_and_missing_fields_stay_failed(self):
        r=record()
        r['test_definition']['variants'][0]['result']['response_schema'] = {
            'type':'array','items':{'type':'object','properties':{
                'op':{'const':'replace'},'path':{'type':'string'},'value':{}},
                'required':['op','path','value'],'additionalProperties':False}}
        ops=json.loads(r['outputs']['patch'])
        cases=[]
        x=copy.deepcopy(ops);x[0]['value']='wrong';cases.append(x)
        x=copy.deepcopy(ops);x[0]['path']='elements.missing.value';cases.append(x)
        x=copy.deepcopy(ops);del x[0]['value'];cases.append(x)
        x=copy.deepcopy(ops);x[0]['op']='unknown';cases.append(x)
        x=copy.deepcopy(ops);x[0]['extra']=True;cases.append(x)
        cases.append(ops+ops)
        for ops in cases:
            for text in spellings(json.dumps(ops)):
                with self.subTest(ops=ops,text=text):
                    self.assertEqual(assess_record(response(r,text),validator=V)['objective_outcome'],'FAIL')

    def test_uncontracted_extra_members_keep_original_policy(self):
        r=record();ops=json.loads(r['outputs']['patch']);ops[0]['extra']=True
        text=json.dumps(ops)
        # The synthetic source fixture has no response schema. Preserve its
        # existing policy; real exact-field contracts are checked separately.
        self.assertEqual(assess_record(response(r,text),validator='dot-separators-v2')['objective_outcome'],'PASS')
        self.assertEqual(assess_record(response(r,text[1:-1]),validator=V)['objective_outcome'],'PASS')

    def test_complete_first_operation_does_not_satisfy_missing_requested_change(self):
        r=record();r['test_definition']['variants'][0]['result']['required_ops']=['replace','replace']
        r['test_definition']['expected_state']['elements'][0]['id']='changed-id'
        text=json.dumps(json.loads(r['outputs']['patch'])[0])
        a=assess_record(response(r,text),validator=V)
        self.assertEqual(a['objective_outcome'],'FAIL')
        self.assertTrue(any(c['code']=='patch.required_operations'and c['status']=='failed'for c in a['checks']))
        self.assertTrue(any(c['code']=='state.final'and c['status']=='failed'for c in a['checks']))

    def test_encoded_quoted_literal_ids_and_malformed_percent_are_not_changed(self):
        r=record();ops=json.loads(r['outputs']['patch'])
        for part in ('a%2Eb','"a.b"','a.b'):
            ops[0]['path']='elements.'+part+'.value'
            self.assertEqual(assess_record(response(r,json.dumps(ops)[1:-1]),validator=V)['objective_outcome'],'PASS')
        ops[0]['path']='elements.a%GG.value'
        self.assertEqual(assess_record(response(r,json.dumps(ops)[1:-1]),validator=V)['objective_outcome'],'FAIL')
        from evaluation import dot_separators_v2 as base
        self.assertIs(get_validator(V).adapter.lower_operation,base.lower_operation)
        self.assertIs(get_validator(V).adapter.apply,base.apply)

    def test_incomplete_and_timeout_calls_never_become_success(self):
        for status in ('timeout','error','cancelled'):
            r=response(record(),record()['outputs']['patch'][1:-1]);r['status']=status
            self.assertNotEqual(assess_record(r,validator=V)['objective_outcome'],'PASS')
        r=response(record(),record()['outputs']['patch'][1:-1]);r['calls'][0]['finish_reason']='length'
        self.assertNotEqual(assess_record(r,validator=V)['objective_outcome'],'PASS')

    def test_replay_preserves_raw_score_generation_and_reuses_validation_identity(self):
        with tempfile.TemporaryDirectory()as tmp:
            r=response(record(),record()['outputs']['patch'][1:-1]);path=ResultStore(Path(tmp)/'source').save(r)
            raw=path.read_bytes();generation=code_fingerprint()
            first=replay(Path(tmp)/'source',Path(tmp)/'output',validator=V)
            snapshot={str(p.relative_to(Path(tmp)/'output')):p.read_bytes()for p in(Path(tmp)/'output').rglob('*.json')}
            second=replay(Path(tmp)/'source',Path(tmp)/'output',validator=V)
            self.assertEqual(first,second);self.assertEqual(path.read_bytes(),raw);self.assertEqual(code_fingerprint(),generation)
            self.assertEqual(snapshot,{str(p.relative_to(Path(tmp)/'output')):p.read_bytes()for p in(Path(tmp)/'output').rglob('*.json')})
            self.assertEqual(first['outcomes'],{'PASS':1});self.assertFalse(first['problems'])
            saved=json.loads(next((Path(tmp)/'output').glob('*/assessments/*.json')).read_text())
            self.assertEqual(saved['original_score'],r['score'])
            self.assertEqual(saved['validation_lineage']['generation_workflow_fingerprint'],'original-generation-identity')

    def test_pure_parser_does_not_claim_dot_paths_are_standard_pointers(self):
        result=normalize_outer_array('{"op":"replace","path":"elements.a.b.value","value":3}')
        self.assertEqual(json.loads(result.to_json())[0]['path'],'elements.a.b.value')

if __name__=='__main__':unittest.main()
