"""Deterministic live runner tests. Never inference or historical regrading."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.live_intent import VERSION, STRICT, configuration, normalize_response, select
from intent_parser import parse_intent
from workbench.domain import validate_test, write_json, digest, experiment_spec, case_id, ResultStore
from workbench.scoring import apply
from workbench.workflows import execute, evaluate
from workbench.live import prepare


def obj(fields):
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}


def fixture():
    schema=obj({'items':{'type':'array','x-id-field':'key','items':obj({
        'key':{'type':'string'},'count':{'type':'number'},'label':{'type':'string'}})},
        'values':{'type':'array','items':{'type':'string'}}})
    initial={'items':[{'key':'a.b','count':1,'label':'keep "replace" and set'}], 'values':['one','two']}
    expected=copy.deepcopy(initial);expected['items'][0]['count']=2
    contract={'type':'array','items':{'oneOf':[
        {'type':'object','properties':{'op':{'const':op},'path':{'type':'string'}, **({'value':{}} if value else {})},
         'required':['op','path']+(['value'] if value else []),'additionalProperties':False}
        for op,value in [('replace',True),('add',True),('remove',False)]]}}
    variant={'id':'normal_json','prompt_style':'direct_text_v1','cache':'default',
        'steps':[{'id':'patch','type':'generate','prompt':'Update the count using the supplied data.','output':{'type':'text'}}],
        'result':{'step':'patch','representation':'dot_patch_v1','required_ops':['replace'],'response_schema':contract}}
    return {'schema_version':2,'id':'synthetic_current_dot','workflow':'steps','enabled':True,'repetitions':1,
        'timeout_seconds':120,'instructions':'','source':{'initial_state':initial},'state_schema':schema,
        'expected_state':expected,'variants':[variant]}


class Backend:
    supports_cache=False
    supports_schema=False
    def __init__(self, text, finish='stop'):
        self.text=text;self.finish=finish;self.calls=[]
    def generate(self, messages, settings, schema, cache='default', cancel=None):
        self.calls.append((messages,settings,schema))
        return {'text':self.text,'finish_reason':self.finish}


class CurrentLiveIntentTests(unittest.TestCase):
    def setUp(self):
        self.strict=fixture()
        self.chosen=select(self.strict)
        self.variant=self.chosen['variants'][0]

    def run_response(self, text, test=None):
        test=test or self.chosen
        before=copy.deepcopy(test)
        backend=Backend(text)
        result=execute(test,test['variants'][0],backend)
        self.assertEqual(test,before)
        self.assertEqual(result['outputs']['patch'],text)
        self.assertEqual(result['calls'][0]['text'],text)
        self.assertEqual(len(backend.calls),1)
        return result['score']

    def test_grammar_spec_is_pinned_in_live_evaluator_identity(self):
        from evaluation.live_intent import identity
        import hashlib
        info = identity()
        source = Path(__file__).resolve().parents[1] / 'intent_parser' / 'grammar-spec.json'
        expected = hashlib.sha256(source.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        self.assertEqual(info['source_hashes']['intent_parser/grammar-spec.json'], expected)

    def test_strict_default_remains_strict_and_selected_live_runner_uses_parser_once(self):
        raw='update path:"items.a.b.count" value:2'
        self.assertFalse(self.run_response(raw,self.strict)['valid'])
        with patch('evaluation.live_intent.normalize_response', wraps=normalize_response) as normalizer:
            score=self.run_response(raw)
        self.assertEqual(normalizer.call_count,1)
        self.assertEqual(normalizer.call_args.args,(raw,self.strict['source']['initial_state'],self.strict['state_schema']))
        self.assertTrue(score['exact_match'],score)
        self.assertTrue(score['patch_ops_match'])
        self.assertTrue(score['response_schema_valid'])
        self.assertEqual(score['actual_patch_ops'],['replace'])
        self.assertEqual(score['evaluation']['normalized_patch'][0]['path'],'items.a%2Eb.count')
        self.assertEqual(score['evaluation']['version'],VERSION)

    def test_valid_strict_json_and_tolerant_wrappers_have_identical_outcome(self):
        raw='[{"op":"replace","path":"items.a%2Eb.count","value":2}]'
        for text in [raw,'```json\n'+raw+'\n```',raw[1:],raw[:-1],raw[1:-1]]:
            with self.subTest(text=text):
                score=self.run_response(text)
                self.assertTrue(score['exact_match'],score)
        self.assertTrue(self.run_response(raw,self.strict)['exact_match'])

    def test_lexical_quoted_percent_and_grouped_components_are_not_reconstructed(self):
        for raw in [
            'update path:"items.\\"a.b\\".count" value:2',
            'update path:items."a.b".count value:2',
            'update path:["items","a.b","count"] value:2',
            'update path:"items.a%2Eb.count" value:2',
        ]:
            with self.subTest(raw=raw):
                self.assertTrue(self.run_response(raw)['exact_match'])
        # Explicit components are literals: %2E here is not an escape.
        self.assertFalse(self.run_response('update path:["items","a%2Eb","count"] value:2')['valid'])

    def test_ambiguity_is_rejected_even_when_one_interpretation_matches_oracle(self):
        schema=obj({'a.b':{'type':'number'},'a':obj({'b':{'type':'number'}})})
        initial={'a.b':1,'a':{'b':2}}
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            normalize_response('update path:"a.b" value:3',initial,schema)
        parsed=normalize_response('update path:["a.b"] value:3',initial,schema)
        self.assertEqual(parsed['final_state'],{'a.b':3,'a':{'b':2}})

    def test_no_positional_or_rfc_bridge_and_explicit_alias_scope(self):
        for text in [
            'update path:"items.0.count" value:2',
            '[{"op":"replace","path":"/items/0/count","value":2}]',
            'move from:["items","a.b"] to:["values"]',
            'copy from:["items","a.b"] to:["values"]',
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.run_response(text)['valid'])
        self.assertTrue(self.run_response('set path:"items.a%2Eb.count" value:2')['valid'])
        self.assertEqual(parse_intent('set path:["x"] value:2'), [{'op': 'update', 'path': ['x'], 'value': 2}])
        for op in ('replace',):
            with self.assertRaises(ValueError):
                parse_intent(op+' path:["x"] value:2')

    def test_atomic_rejection_bad_roles_unknown_fields_schema_and_duplicates(self):
        for operations in [
            [{'op':'replace','path':'items','value':[]}],
            [{'op':'replace','path':'items.a%2Eb','value':{'key':'a.b','count':2,'label':'x'}}],
            [{'op':'remove','path':'items.a%2Eb.label'}],
            [{'op':'add','path':'values','value':'one'}],
            [{'op':'replace','path':'items.a%2Eb.count','value':'2'}],
            [{'op':'add','path':'items','value':{'key':'new','count':1}}],
            [{'op':'replace','path':'items.a%2Eb.count','value':2,'extra':True}],
            [{'op':'replace','path':'items.a%2Eb.count','value':2},{'op':'remove','path':'missing'}],
        ]:
            with self.subTest(operations=operations):
                self.assertFalse(self.run_response(json.dumps(operations))['valid'])

    def test_operation_and_response_schema_checks_use_normalized_response_not_only_state(self):
        test=copy.deepcopy(self.chosen);test['variants'][0]['result']['required_ops']=['add']
        score=self.run_response('update path:["items","a.b","count"] value:2',test)
        self.assertTrue(score['valid']);self.assertTrue(score['state_exact_match']);self.assertFalse(score['exact_match'])
        test=copy.deepcopy(self.chosen);test['variants'][0]['result']['response_schema']={'type':'array','maxItems':0}
        score=self.run_response('update path:["items","a.b","count"] value:2',test)
        self.assertTrue(score['state_exact_match']);self.assertFalse(score['response_schema_valid']);self.assertFalse(score['exact_match'])

    def test_no_change_is_explicit_and_wrong_oracle_does_not_change_normalization(self):
        test=copy.deepcopy(self.chosen);test['expected_state']=copy.deepcopy(test['source']['initial_state'])
        test['variants'][0]['result']['required_ops']=[]
        self.assertTrue(self.run_response('[]',test)['exact_match'])
        for text in ('','  ','; ',',','{}','()','[,]','[',']','none','[{"op":"remove","path":"missing"}]'):
            with self.subTest(text=text):
                self.assertFalse(self.run_response(text,test)['exact_match'])
        score=self.run_response('update path:["items","a.b","count"] value:2',test)
        self.assertTrue(score['valid']);self.assertFalse(score['exact_match'])
        self.assertEqual(score['evaluation']['normalized_patch'][0]['value'],2)

    def test_values_are_not_rewritten_and_per_collection_id_keys_are_used(self):
        raw='[{"op":"add","path":"items","value":{"key":"x.y","count":3,"label":"replace set items.a.b \\u2603"}}]'
        before=copy.deepcopy(self.strict['source']['initial_state'])
        result=normalize_response(raw,before,self.strict['state_schema'])
        self.assertEqual(result['final_state']['items'][-1],json.loads(raw)[0]['value'])
        self.assertEqual(before,self.strict['source']['initial_state'])

    def test_numeric_lexemes_survive_values_and_grouped_selectors(self):
        schema=obj({'values':{'type':'array','items':{'type':['string','number']}}})
        result=normalize_response('add path:"values" value:2; remove path:"values.2"',{'values':[1]},schema)
        self.assertEqual(result['final_state'],{'values':[1]})
        self.assertIs(type(result['normalized_patch'][0]['value']),int)
        self.assertEqual(normalize_response('remove path:["values",1]',{'values':[1]},schema)['final_state'],{'values':[]})
        self.assertEqual(normalize_response('remove path:["values",1.0]',{'values':[1.0]},schema)['final_state'],{'values':[]})
        with self.assertRaises(ValueError):
            normalize_response('remove path:["values",1.0]',{'values':[1]},schema)

    def test_ambiguous_typed_identities_remain_rejected(self):
        schema=obj({'values':{'type':'array','items':{'type':['string','number']}}})
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            normalize_response('[]',{'values':[1,'1']},schema)

    def test_stale_unknown_or_inapplicable_config_rejected_before_generation(self):
        for edit in ('fingerprint','version','representation','output'):
            test=copy.deepcopy(self.chosen);v=test['variants'][0]
            if edit in ('fingerprint','version'):v['result']['evaluator'][edit]='unknown'
            elif edit=='representation':v['result']['representation']='value_patch'
            else:v['steps'][0]['output']={'type':'json'}
            backend=Backend('[]')
            with self.subTest(edit=edit),self.assertRaises(ValueError):
                execute(test,v,backend)
            self.assertFalse(backend.calls)

    def test_malformed_explicit_selection_is_not_silently_strict(self):
        for config in (None, VERSION, {}, {'version':VERSION}):
            test=copy.deepcopy(self.strict);variant=test['variants'][0]
            variant['result']['evaluator']=config
            with self.subTest(config=config):
                with self.assertRaises(ValueError):validate_test(test)
                with self.assertRaises(ValueError):execute(test,variant,Backend('[]'))
                self.assertFalse(evaluate(test,variant,{'patch':'[]'})['valid'])

    def test_prepare_keeps_rejected_source_definition_blocked(self):
        from workbench.judgements import JudgementStore,definition_id
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'test_specs'
            write_json(source/'test.json',self.strict)
            store=JudgementStore(root)
            store.update([definition_id(self.strict,self.strict['variants'][0])],'rejected','Synthetic rejection','test')
            with self.assertRaisesRegex(ValueError,'No enabled'):
                prepare(source,root.parent/(root.name+'-unused-output'),VERSION)

    def test_incomplete_generation_never_becomes_valid_intent(self):
        result=execute(self.chosen,self.variant,Backend('[]','length'))
        self.assertFalse(result['score']['valid'])
        self.assertNotIn('evaluation',result['score'])

    def test_selection_preserves_prompts_and_creates_distinct_identity(self):
        before=copy.deepcopy(self.strict)
        validate_test(self.chosen)
        self.assertEqual(self.strict,before)
        self.assertEqual(self.variant['steps'],before['variants'][0]['steps'])
        model={'id':'synthetic','files':['synthetic.gguf'],'required_vram_gb':8};target={'vram_gb':8}
        old=case_id(model,self.strict,self.strict['variants'][0],0,target)
        new=case_id(model,self.chosen,self.variant,0,target)
        self.assertNotEqual(old,new)
        self.assertEqual(select(self.chosen,STRICT),self.strict)

    def test_prepare_is_explicit_new_directory_never_rewrites_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir()
            write_json(source/'test.json',self.strict);before=(source/'test.json').read_bytes()
            output=Path(tmp)/'selected'
            report=prepare(source,output,VERSION)
            self.assertEqual(report['tests'],1);self.assertEqual(report['variants'],1)
            self.assertFalse(report['inference_started'])
            self.assertEqual((source/'test.json').read_bytes(),before)
            with self.assertRaises(ValueError):prepare(source,output,VERSION)
            with self.assertRaises(ValueError):prepare(source,source/'inside',VERSION)

    def test_retired_field_value_contract_is_not_an_alternate_decoder(self):
        initial=self.strict['source']['initial_state'];schema=self.strict['state_schema']
        for text in ('set: items.a%2Eb.count\nvalue: 2', 'set: items.0.count\nvalue: 2'):
            with self.assertRaisesRegex(ValueError, 'Retired response contract field_value_v2'):
                apply(initial,text,'field_value_v2',schema)

    def test_controller_session_persistence_and_resume_use_new_parser(self):
        from workbench.controller import Controller
        from workbench.demo_native import DemoNative
        raw='update path:"items.a.b.count" value:2'
        calls=[]
        def generate(backend,messages,settings,schema,cache='default',cancel=None):
            calls.append(messages)
            return {'text':raw,'finish_reason':'stop','cached_tokens':0}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_json(root/'test_specs/test.json',self.chosen)
            app=Controller(root,True)
            with patch.object(DemoNative,'generate',generate):
                app.run(selection={'model_id':'demo-2b','test_id':self.chosen['id']})
                records=app.store.all()
                self.assertEqual(len(records),1,app.message)
                self.assertTrue(records[0]['score']['exact_match'],records[0])
                self.assertEqual(records[0]['calls'][0]['text'],raw)
                self.assertEqual(records[0]['outputs']['patch'],raw)
                self.assertEqual(records[0]['variant_definition']['result']['evaluator'],configuration())
                snapshots={p:p.read_bytes() for p in app.store.root.rglob('*.json')}
                app.run(selection={'model_id':'demo-2b','test_id':self.chosen['id']})
                self.assertEqual(len(calls),1)
                self.assertEqual(snapshots,{p:p.read_bytes() for p in app.store.root.rglob('*.json')})
                # Switching back never reuses the new intent-mode observation.
                write_json(root/'test_specs/test.json',self.strict)
                app.run(selection={'model_id':'demo-2b','test_id':self.strict['id']})
                self.assertEqual(len(calls),2)
                self.assertEqual(len(app.store.all()),2)
                self.assertEqual(sum(r['score']['exact_match'] for r in app.store.all()),1)
                strict_bytes={p:p.read_bytes() for p in app.store.root.rglob('*.json')}
                app.run(selection={'model_id':'demo-2b','test_id':self.strict['id']})
                self.assertEqual(len(calls),2)  # completed wrong answer is terminal too
                self.assertEqual(strict_bytes,{p:p.read_bytes() for p in app.store.root.rglob('*.json')})


if __name__=='__main__':
    unittest.main()
