"""Independent dot-path examples and original-baseline builder integration."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.core import assess
from test_builder.builder import ROOT, compile_test, build_messages, oracle
from test_builder.original_prompt import baseline
from workbench.domain import read_json
from workbench.dot_paths import encode_part, normalize_operation, normalize_path, resolve, validate, from_pointer, full_paths
from workbench.scoring import apply
from workbench.workflows import evaluate, execute


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


class DotPathTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read_json(ROOT/'fixtures.json')['fixtures']
        self.fixture = next(f for f in self.fixtures if f['id']=='db_v3_update_record')

    def test_original_renderer_reconstructs_all_59_unchanged_original_requests(self):
        count=0
        with patch('test_builder.normal_prompt.configuration',side_effect=AssertionError('OPRO templates must not be consulted')):
            for fixture in self.fixtures:
                if fixture['task']=='no_change':continue
                original=baseline()['messages'][fixture['id']+'__value_patch']
                for mode,expected in original.items():
                    self.assertEqual(build_messages(fixture,mode,method='original_value_patch_v1'),expected)
                    count+=1
        self.assertEqual(count,59)

    def test_all_62_dot_requests_have_independent_passing_references_and_no_optimized_guidance(self):
        checked=0
        for fixture in self.fixtures:
            test=compile_test(fixture,method='dot_patch_v1')
            self.assertFalse(test['enabled'])
            self.assertEqual(test['instructions'],'')
            self.assertFalse(test['prompt_builder']['baseline_provenance']['opro_guidance'])
            reference,expected=oracle(fixture,'dot_patch_v1')
            self.assertEqual(apply(fixture['state'],reference,'dot_patch_v1',fixture['schema']),expected)
            self.assertEqual(expected,oracle(fixture)[1])
            for variant in test['variants']:
                text=variant['steps'][0]['prompt'];checked+=1
                from test_builder.builder import prompt_parts
                control=prompt_parts(fixture,variant['id'],method='original_value_patch_v1')
                self.assertEqual(variant['prompt_bindings']['current_state'],control['current_state'])
                self.assertEqual(variant['result']['representation'],'dot_patch_v1')
                self.assertNotIn('Task-specific',text);self.assertNotIn('Earlier workflow outputs',text)
                self.assertNotIn('selector quotation',text);self.assertNotIn('Append a slash',text)
                self.assertEqual(text.count('Only these five operations are allowed:'),1)
                self.assertEqual(evaluate(test,variant,{'patch':json.dumps(reference)})['exact_match'],True)
                self.assertEqual(assess(test,variant,{'patch':json.dumps(reference)})['objective_outcome'],'PASS')
                if fixture['task']=='no_change':
                    self.assertIn('The documentation uses blue headings and a serif font.',text)
                    self.assertNotEqual(text,baseline()['messages'][fixture['id']+'__value_patch'][variant['id']][-1]['content'])
        self.assertEqual(checked,62)

    def test_plain_ids_are_resolved_against_data_not_positions(self):
        state=self.fixture['state'];schema=self.fixture['schema']
        self.assertEqual(resolve(state,schema,'items.item-17.count')[0],8)
        for path in ('items.1.count','items.@item-17.count','/items/item-17/count','items..count','items.'):
            with self.subTest(path=path),self.assertRaises(ValueError):resolve(state,schema,path)
        with self.assertRaises(ValueError):apply(state,[{'op':'replace','path':'/items/item-17/count','value':9}],'value_patch',schema)

    def test_path_only_quote_normalization_preserves_every_data_quote(self):
        value={'name':'He said "a.b"','path':'keep.this', 'from':'"literal"'}
        operation={'op':'add','path':'"items"','value':value}
        normalized=normalize_operation(operation)
        self.assertEqual(normalized['path'],'items');self.assertEqual(normalized['value'],value)
        self.assertEqual(operation['path'],'"items"')
        test=compile_test(self.fixture,method='dot_patch_v1');variant=test['variants'][0]
        raw=json.dumps([{'op':'replace','path':'items."item-17".count','value':9}])
        self.assertTrue(evaluate(test,variant,{'patch':raw})['exact_match'])
        self.assertEqual(assess(test,variant,{'patch':raw})['objective_outcome'],'PASS')
        with self.assertRaises(ValueError):normalize_path('items."unterminated')
        # Unused fields retain the existing method's semantics and are not data to rewrite.
        self.assertEqual(apply(self.fixture['state'],[{'op':'replace','path':'items.item-17.count','from':None,'value':9}],'dot_patch_v1',self.fixture['schema']),oracle(self.fixture)[1])

    def test_reserved_characters_empty_ids_unicode_and_literal_at_round_trip(self):
        for identifier in ('a.b','a/b','a%2Eb','a"b','a\\b','@id','', 'snow \u2603',':','%_'):
            with self.subTest(identifier=identifier):
                state={'a.b':[{'id':identifier,'value':'quoted "text"'}]}
                schema=obj({'a.b':{'type':'array','x-id-field':'id','items':obj({'id':{'type':'string'},'value':{'type':'string'}})}})
                path='a%2Eb.'+encode_part(identifier)+'.value'
                self.assertNotIn('"',path);self.assertNotIn('@',path)
                self.assertEqual(resolve(state,schema,path)[0],'quoted "text"')
                self.assertEqual(from_pointer(state,schema,'/a.b/0/value'),path)
                self.assertIn(path+':"quoted \\"text\\""',full_paths(state,schema))
                updated=apply(state,[{'op':'replace','path':path,'value':'next "value"'}],'dot_patch_v1',schema)
                self.assertEqual(updated['a.b'][0]['value'],'next "value"')
        self.assertEqual(normalize_path('"a.b"."@id".value'),'a%2Eb.%40id.value')
        self.assertEqual(resolve({'':7},obj({'':{'type':'number'}}),'%_')[0],7)
        for bad in ('a%ZZ','a%','a%FF','a b','a/b','@id'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):normalize_path(bad)

    def test_mixed_scalar_types_are_not_guessed_and_ambiguous_text_is_rejected(self):
        schema=obj({'values':{'type':'array','uniqueItems':True,'items':{'type':['string','number','boolean','null']}}})
        state={'values':[42,'other',False,None,0]}
        for spelling,value in [('42',42),('other','other'),('false',False),('null',None),('0',0)]:
            selected=resolve(state,schema,'values.'+spelling)[0]
            self.assertIs(type(selected),type(value));self.assertEqual(selected,value)
        for values,spelling in [([42,'42'],'42'),([False,'false'],'false'),([None,'null'],'null')]:
            ambiguous={'values':values}
            with self.subTest(values=values),self.assertRaisesRegex(ValueError,'Ambiguous'):resolve(ambiguous,schema,'values.'+spelling)
            with self.assertRaisesRegex(ValueError,'Ambiguous'):validate(ambiguous,schema)
            with self.assertRaisesRegex(ValueError,'Ambiguous'):apply(ambiguous,[],'dot_patch_v1',schema)

    def test_nested_collections_sequential_identity_changes_copy_and_move(self):
        element=obj({'id':{'type':'string'},'value':{'type':'string'}})
        collection={'type':'array','items':element,'x-id-field':'id'}
        schema=obj({'a':collection,'b':collection})
        initial={'a':[{'id':'old','value':'untouched'}],'b':[]}
        operations=[{'op':'replace','path':'a.old.id','value':'new.id'},
                    {'op':'copy','from':'a.new%2Eid','path':'b'},
                    {'op':'replace','path':'b.new%2Eid.value','value':'changed'}]
        expected={'a':[{'id':'new.id','value':'untouched'}],'b':[{'id':'new.id','value':'changed'}]}
        self.assertEqual(apply(initial,operations,'dot_patch_v1',schema),expected)
        self.assertEqual(initial,{'a':[{'id':'old','value':'untouched'}],'b':[]})
        self.assertEqual(apply(initial,[{'op':'move','from':'a.old','path':'b'}],'dot_patch_v1',schema),{'a':[],'b':[{'id':'old','value':'untouched'}]})
        for op in ({'op':'move','from':'a.old','path':'a'},{'op':'copy','from':'a.old.value','path':'b'}, {'op':'remove','path':'a.old.value'}, {'op':'replace','path':'a.old','value':initial['a'][0]}):
            with self.subTest(op=op),self.assertRaises(ValueError):apply(initial,[op],'dot_patch_v1',schema)

    def test_mock_execution_is_repeatable_and_export_resume_is_byte_stable(self):
        fixture=self.fixture;test=compile_test(fixture,method='dot_patch_v1');variant=test['variants'][0];calls=[]
        class Backend:
            supports_cache=False;supports_schema=False
            def generate(self,request,settings,schema,cache,cancel):
                calls.append(request);return {'text':json.dumps(oracle(fixture,'dot_patch_v1')[0]),'finish_reason':'stop'}
        self.assertTrue(execute(test,variant,Backend())['score']['exact_match'])
        self.assertTrue(execute(test,variant,Backend())['score']['exact_match'])
        self.assertEqual(calls[0],calls[1])
        from test_builder.dot_experiment import build
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);first=build(root)
            before={p.relative_to(root):p.read_bytes()for p in root.rglob('*')if p.is_file()}
            second=build(root)
            self.assertEqual(first,second);self.assertEqual(first['prompts'],62)
            self.assertEqual(before,{p.relative_to(root):p.read_bytes()for p in root.rglob('*')if p.is_file()})


if __name__=='__main__':unittest.main()
