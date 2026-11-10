"""Source-JS conformance and unchanged semantic-oracle checks; no model calls."""
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from evaluation.core import assess
from test_builder.builder import ROOT,compile_test,oracle
from test_builder.ember_prompt import support_reason,provenance
from test_builder.ember_experiment import build
from workbench.domain import read_json,validate_test
from workbench.ember_text import parse,apply,decode,full_paths
from workbench.scoring import equal
from workbench.workflows import evaluate,execute,messages

VALID=[
 'none',' \ufeffnone\n','set: /a\ntext:', 'set: /a\ntext: hello: world',
 'set: /a\ntext: {"literal":true}', 'set: /a\ntext: "literal quotes"',
 'set: /a\ntext: leading  and  trailing  \n\nset: /b\ntext: last',
 'set: /a\ntext:  two leading spaces', 'set: /a\ntext: false',
 'set: /a\nnumber: +2','set: /a\nnumber: -0','set: /a\nnumber: -12.25',
 'set: /a\nnumber: 9007199254740993','set: /a\nboolean: false','set: /a\nboolean: true',
 'set: /a\nnull:', 'set: /a\nlist: \t\n\nset: /b\nobject:\t',
 'append: /a\ntext: one\nappend: /a\ntext: two','remove: /a',
 'change: /a\nnumber: 1\n\nset: /a\nnumber: 4',
 'set: /key~1ring~0mark\ntext: x','set: /a.b/with spaces/雪\ntext: snow ☃',
 'set: /a\r\ntext: CRLF\r\n\r\nremove: /b',
 'set: /a\ntext: final spaces are trimmed   ',
 'set: /a~01b\ntext: exact escape order',
]
INVALID=[
 '', ' ', '{}','[]','```\nnone\n```','None','none\nset: /a\ntext: x',
 'set: a\ntext: x','set: /\ntext: x','set: /a//b\ntext: x','set: /a/~2\ntext: x',
 'set: /constructor/x\ntext: x','set: /a/__proto__/x\ntext: x','set: /prototype\ntext: x',
 'set: /a','set: /a\n\ntext: x','set: /a\nnumber: 01','set: /a\nnumber: 1e2',
 'set: /a\nnumber: .2','set: /a\nnumber: Infinity','set: /a\nnumber: NaN',
 'set: /a\nnumber: ١','set: /a\nnumber: '+('9'*400),
 'set: /a\nboolean: yes','set: /a\nnull: value','set: /a\nobject: {}','set: /a\nlist: []',
 'change: /a\ntext: 1','remove: /a\ntext: x','move: /a\ntext: /b','copy: /a\ntext: /b',
 'set: /a\ntext: x\nset: /a\ntext: y','set: /a\ntext: x\n  set: /b\ntext: y',
 'set: /a\ntext: first\nsecond','set: /a\ntext: x\u2028y',
]

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}

class EmberTextTests(unittest.TestCase):
    def setUp(self):self.fixtures=read_json(ROOT/'fixtures.json')['fixtures']

    def test_vendored_source_hash_and_js_parser_conformance(self):
        source=ROOT/'reference/ember_ai_response_text_v1.js'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),provenance()['sha256'])
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable: independent source-JS conformance must be run before live method inference')
        code="const fs=require('fs'),c=require(process.argv[1]);process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(s=>{try{return {ok:true,value:c.operations(s)}}catch(e){return {ok:false}}})));"
        cases=VALID+INVALID
        result=subprocess.run([node,'-e',code,str(source)],input=json.dumps(cases),capture_output=True,text=True,encoding='utf8',check=True)
        expected=json.loads(result.stdout)
        for raw,reference in zip(cases,expected):
            with self.subTest(raw=raw):
                try:actual={'ok':True,'value':parse(raw)}
                except ValueError:actual={'ok':False}
                self.assertEqual(actual['ok'],reference['ok'])
                if actual['ok']:self.assertTrue(equal(actual['value'],reference['value']))
        self.assertTrue(all(x['ok']for x in expected[:len(VALID)]))
        self.assertTrue(all(not x['ok']for x in expected[len(VALID):]))

    def test_source_grouping_nullification_and_literal_values(self):
        state={'count':0,'note':'before','maybe':'present','values':[]}
        schema=obj({'count':{'type':'number'},'note':{'type':'string'},'maybe':{'type':['string','null']},
                    'values':{'type':'array','uniqueItems':True,'items':{'type':'string'}}})
        raw='change: /count\nnumber: 1\n\nset: /count\nnumber: 10\n\nremove: /maybe\n\nset: /note\ntext: {"literal":true}\n\nappend: /values\ntext: 42'
        result=apply(state,raw,schema)
        self.assertEqual(result,{'count':11,'note':'{"literal":true}','maybe':None,'values':['42']})
        self.assertEqual(state['maybe'],'present');self.assertIn('maybe',result)

    def test_existing_schema_and_operation_roles_are_not_relaxed(self):
        fixture=next(f for f in self.fixtures if f['task']=='append_value')
        before=copy.deepcopy(fixture['state'])
        for raw in ('append: /locations\ntext: town-a','set: /locations\nlist:','set: /unknown\ntext: x',
                    'set: /locations/0\ntext: changed','set: /locations/town-a\ntext: changed',
                    'append: /locations\nobject:','append: /locations\nboolean: true'):
            with self.subTest(raw=raw),self.assertRaises(Exception):apply(before,raw,fixture['schema'])
        self.assertEqual(before,fixture['state'])

    def test_all_supported_fixtures_match_independent_reference_and_same_oracle(self):
        # Handwritten responses are independent of the new reference emitter.
        answers={'db_v3_update_field':'set: /profile/hair\ntext: black',
                 'db_v3_append_value':'append: /locations\ntext: town-d',
                 'db_v3_append_value_empty':'append: /locations\ntext: town-a','db_v3_no_change':'none'}
        checked=0;unsupported=[]
        for fixture in self.fixtures:
            reason=support_reason(fixture)
            if reason:
                unsupported.append(fixture['id'])
                with self.assertRaisesRegex(ValueError,'Unsupported Ember fixture'):compile_test(fixture,method='ember_text_v1')
                continue
            test=compile_test(fixture,method='ember_text_v1');validate_test(test)
            self.assertFalse(test['enabled']);self.assertEqual(test['source']['initial_state'],fixture['state'])
            self.assertEqual(test['expected_state'],oracle(fixture)[1])
            raw=answers[fixture['id']];emitted,expected=oracle(fixture,'ember_text_v1')
            self.assertEqual(emitted,raw);self.assertTrue(equal(apply(fixture['state'],raw,fixture['schema']),expected))
            for variant in test['variants']:
                score=evaluate(test,variant,{'patch':raw});detail=assess(test,variant,{'patch':raw});checked+=1
                self.assertTrue(score['exact_match']);self.assertEqual(detail['objective_outcome'],'PASS')
                self.assertFalse(any(c['code']=='json.document'for c in detail['checks']))
                for bad in ('[]','```\n'+raw+'\n```','Explanation\n'+raw):
                    self.assertFalse(evaluate(test,variant,{'patch':bad})['exact_match'])
                    self.assertEqual(assess(test,variant,{'patch':bad})['objective_outcome'],'FAIL')
        self.assertEqual((checked,len(unsupported)),(11,17))

    def test_empty_noop_and_redundant_writes_keep_operation_requirement(self):
        fixture=next(f for f in self.fixtures if f['task']=='no_change');test=compile_test(fixture,method='ember_text_v1');v=test['variants'][0]
        self.assertTrue(evaluate(test,v,{'patch':'none'})['exact_match'])
        self.assertFalse(evaluate(test,v,{'patch':''})['exact_match'])
        # A new unrelated fact remains a mutation, never silently discarded.
        self.assertFalse(evaluate(test,v,{'patch':'append: /items\ntext: invented'})['exact_match'])

    def test_pointer_encoding_and_native_full_paths_have_no_array_selectors(self):
        initial={'a.b/雪':{'x~y':'old'},'values':['a.b','a/b']}
        schema=obj({'a.b/雪':obj({'x~y':{'type':'string'}}),'values':{'type':'array','uniqueItems':True,'items':{'type':'string'}}})
        result=apply(initial,'set: /a.b~1雪/x~0y\ntext: new: "literal"',schema)
        self.assertEqual(result['a.b/雪']['x~y'],'new: "literal"')
        self.assertEqual(full_paths(initial),['/a.b~1雪/x~0y:"old"','/values:["a.b","a/b"]'])

    def test_mock_workflow_uses_exact_reviewed_plaintext_request_without_json_schema_generation(self):
        fixture=next(f for f in self.fixtures if f['task']=='update_field');test=compile_test(fixture,method='ember_text_v1');v=test['variants'][0];seen=[]
        class Backend:
            supports_cache=False;supports_schema=False
            def generate(self,request,settings,schema,cache,cancel):
                seen.append((request,schema));return {'text':'set: /profile/hair\ntext: black','finish_reason':'stop'}
        self.assertTrue(execute(test,v,Backend())['score']['exact_match'])
        self.assertEqual(seen,[(messages(test,v['steps'][0],{},v),None)])

    def test_examples_are_not_fixture_answers_and_unsupported_scopes_are_visible(self):
        fixture=next(f for f in self.fixtures if f['task']=='update_field');test=compile_test(fixture,method='ember_text_v1')
        for v in test['variants']:
            instructions=v['prompt_bindings']['task_requirements']
            self.assertNotIn('set: /profile/hair',instructions)
            self.assertNotIn('append: /locations',instructions)
            self.assertIn('set: /example/status',instructions)
            self.assertIn('change: /example/count',instructions)
            self.assertIn('You may append a primitive value to an existing collection.',instructions)
            for bookkeeping in ('Adding or removing','unsupported','excluded','research operations','groups operations','Move','Copy','Remove'):
                self.assertNotIn(bookkeeping,instructions)
            self.assertEqual(v['steps'][0]['output']['type'],'text')
        with tempfile.TemporaryDirectory()as folder:
            first=build(folder);snapshot={str(p.relative_to(folder)):p.read_bytes()for p in Path(folder).rglob('*')if p.is_file()}
            second=build(folder)
            self.assertEqual(first,second);self.assertEqual((first['definitions'],first['prompt_presentations'],first['observations_per_model']),(4,11,33))
            self.assertEqual(len(first['unsupported']),17)
            self.assertEqual(snapshot,{str(p.relative_to(folder)):p.read_bytes()for p in Path(folder).rglob('*')if p.is_file()})
            self.assertTrue(all(not t['enabled']for p in(Path(folder)/'test_specs').glob('*.json')for t in[read_json(p)]))

if __name__=='__main__':unittest.main()
