"""Independent examples for value-based paths, including primitive collections."""
import copy
import json
import unittest
from jsonschema.exceptions import ValidationError
from evaluation.core import assess
from workbench.scoring import apply, score_state
from workbench.value_paths import from_pointer, resolve, tokens
from workbench.workflows import evaluate


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def records():
    return {'type':'array','x-id-field':'key','items':obj({'key':{'type':['string','number']},'count':{'type':'number'}})}


class ValuePathTests(unittest.TestCase):
    def setUp(self):
        self.schema = obj({'items':records(),'storage':records(),
            'values':{'type':'array','items':{'type':['string','number','boolean','null']},'uniqueItems':True}})
        self.state = {'items':[{'key':'item-7','count':1},{'key':'item-2','count':2}],
                      'storage':[], 'values':[42,'42',False,None,0,'','a/b','a~b','a"b','a\\b','-']}

    def run_patch(self, patch):
        original=copy.deepcopy(self.state)
        result=apply(self.state,patch,'value_patch',self.schema)
        self.assertEqual(self.state,original)
        return result

    def test_record_update_primitive_remove_append_and_move_have_literal_expected_states(self):
        after=self.run_patch([{'op':'replace','path':'/items/"item-2"/count','value':8},
            {'op':'remove','path':'/values/42'}, {'op':'add','path':'/storage','value':{'key':'new','count':3}},
            {'op':'move','from':'/items/"item-7"','path':'/storage'}])
        self.assertEqual(after['items'],[{'key':'item-2','count':8}])
        self.assertEqual(after['storage'],[{'key':'new','count':3},{'key':'item-7','count':1}])
        self.assertEqual(after['values'],self.state['values'][1:])

    def test_all_scalar_types_use_exact_typed_values_never_indexes(self):
        for value in self.state['values']:
            with self.subTest(value=value):
                path='/values/'+json.dumps(value)
                selected,_,position=resolve(self.state,self.schema,path)
                self.assertIs(type(selected),type(value))
                self.assertEqual(selected,value)
                after=self.run_patch([{'op':'remove','path':path}])
                expected=self.state['values'][:]
                expected.pop(int(position[-1]))
                self.assertEqual(after['values'],expected)
        # 0 is present at position 4; it must not select position zero or False.
        self.assertEqual(resolve(self.state,self.schema,'/values/0')[2],['values','4'])
        with self.assertRaises(ValueError):resolve(self.state,self.schema,'/items/0')

    def test_quoted_ids_slashes_quotes_backslashes_and_tildes_are_literal(self):
        for identifier in ('item/17','a"b','a\\b','~1','',42,'42'):
            with self.subTest(identifier=identifier):
                self.state['items'][1]['key']=identifier
                path='/items/'+json.dumps(identifier)+'/count'
                self.assertEqual(tokens(path),['items',json.dumps(identifier),'count'])
                self.assertEqual(self.run_patch([{'op':'replace','path':path,'value':9}])['items'][1]['count'],9)
                self.assertEqual(from_pointer(self.state,self.schema,'/items/1/count'),path)

    def test_quoted_property_names_and_pointer_escapes_are_equivalent(self):
        self.state={'a/b':{'~key':1},'"quoted':2,'':3}
        self.schema=obj({'a/b':obj({'~key':{'type':'number'}}),'"quoted':{'type':'number'},'':{'type':'number'}})
        for path in ('/a~1b/~0key','/"a/b"/"~key"'):
            self.assertEqual(self.run_patch([{'op':'replace','path':path,'value':7}])['a/b']['~key'],7)
        self.assertEqual(self.run_patch([{'op':'replace','path':'/','value':4}])[''],4)
        path=from_pointer(self.state,self.schema,'/"quoted')
        self.assertEqual(resolve(self.state,self.schema,path)[0],2)

    def test_nested_collections_and_paths_resolve_after_each_change(self):
        self.schema=obj({'groups':{'type':'array','x-id-field':'name','items':obj({'name':{'type':'string'},'items':records()})}})
        self.state={'groups':[{'name':'g/1','items':[{'key':'first','count':1},{'key':'second','count':2}]},
                              {'name':'g2','items':[]}]}
        patch=[{'op':'remove','path':'/groups/"g/1"/items/"first"'},
               {'op':'replace','path':'/groups/"g/1"/items/"second"/key','value':'renamed'},
               {'op':'move','from':'/groups/"g/1"/items/"renamed"','path':'/groups/"g2"/items'},
               {'op':'replace','path':'/groups/"g2"/items/"renamed"/count','value':9}]
        after=self.run_patch(patch)
        self.assertEqual(after['groups'][0]['items'],[])
        self.assertEqual(after['groups'][1]['items'],[{'key':'renamed','count':9}])

    def test_invalid_selectors_missing_matches_and_indexes_fail_without_changing_data(self):
        for path in ('items/"item-2"','/items/"unclosed','/items/"item-2"junk/count',
                     '/items/item-2/count','/items/@"item-2"/count','/items/1/count',
                     '/items/"missing"/count','/items/"item-2"/absent','/values/NaN',
                     '/values/{}','/values/[]','/values/01','/values/1/field'):
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                self.run_patch([{'op':'remove','path':path}])

    def test_duplicate_missing_or_wrong_type_ids_and_schema_violations_fail(self):
        for mutation in ('duplicate','missing','type'):
            original=copy.deepcopy(self.state)
            if mutation=='duplicate':self.state['items'][1]['key']='item-7'
            elif mutation=='missing':self.state['items'][1].pop('key')
            else:self.state['items'][1]['key']=True
            with self.subTest(mutation=mutation),self.assertRaises((ValueError,ValidationError)):self.run_patch([])
            self.state=original
        for item in ({'op':'add','path':'/items','value':{'key':'item-7','count':0}},
                     {'op':'add','path':'/items','value':{'key':'new'}},
                     {'op':'replace','path':'/items/"item-2"/count','value':'wrong'},
                     {'op':'replace','path':'/items/"item-2"/key','value':'item-7'}):
            with self.subTest(item=item),self.assertRaises((ValueError,ValidationError)):self.run_patch([item])

    def test_only_allowed_operation_roles_and_cross_collection_moves(self):
        for item in ({'op':'replace','path':'','value':self.state},
                     {'op':'replace','path':'/items','value':[]},
                     {'op':'replace','path':'/items/"item-2"','value':{'key':'item-2','count':8}},
                     {'op':'remove','path':'/items/"item-2"/count'},
                     {'op':'add','path':'/items/-','value':{'key':'new','count':0}},
                     {'op':'add','path':'/items/2','value':{'key':'new','count':0}},
                     {'op':'move','from':'/items/"item-2"','path':'/items'},
                     {'op':'move','from':'/items/"item-2"/count','path':'/values'},
                     {'op':'copy','from':'/items/"item-2"','path':'/items'},
                     {'op':'test','path':'/items/"item-2"/count','value':2}):
            with self.subTest(item=item),self.assertRaises(ValueError):self.run_patch([item])
        self.state['storage']=[{'key':'item-2','count':5}]
        with self.assertRaises(ValueError):self.run_patch([{'op':'move','from':'/items/"item-2"','path':'/storage'}])

    def test_copy_appends_complete_element_and_updates_do_not_alias_source(self):
        self.state['storage'] = [{'key':'existing','count':7}]
        copied = self.run_patch([{'op':'copy','from':'/items/"item-2"','path':'/storage'}])
        self.assertEqual(copied['items'], self.state['items'])
        self.assertEqual(copied['storage'], [{'key':'existing','count':7},{'key':'item-2','count':2}])
        changed = self.run_patch([{'op':'copy','from':'/items/"item-2"','path':'/storage'},
                                  {'op':'replace','path':'/storage/"item-2"/count','value':99}])
        self.assertEqual(changed['items'], self.state['items'])
        self.assertEqual(changed['storage'][-1]['count'],99)

    def test_primitive_copies_preserve_json_type_and_source(self):
        schema=obj({'a':{'type':'array','items':{'type':['string','number','boolean','null']},'uniqueItems':True},
                    'b':{'type':'array','items':{'type':['string','number','boolean','null']},'uniqueItems':True}})
        for value in (42,'42',False,None,'a/b'):
            with self.subTest(value=value):
                state={'a':[value], 'b':[]}
                after=apply(state,[{'op':'copy','from':'/a/'+json.dumps(value),'path':'/b'}],'value_patch',schema)
                self.assertEqual(after,{'a':[value],'b':[value]})
                self.assertIs(type(after['b'][0]),type(value))
                self.assertEqual(state,{'a':[value],'b':[]})

    def test_invalid_copy_targets_sources_and_duplicate_ids_fail_atomically(self):
        for item in ({'op':'copy','path':'/storage'},
                     {'op':'copy','from':17,'path':'/storage'},
                     {'op':'copy','from':'/items/"missing"','path':'/storage'},
                     {'op':'copy','from':'/items/"item-2"/count','path':'/values'},
                     {'op':'copy','from':'/items/"item-2"','path':'/storage/-'},
                     {'op':'copy','from':'/items/"item-2"','path':'/storage/0'},
                     {'op':'copy','from':'/items/"item-2"','path':'/items'}):
            original=copy.deepcopy(self.state)
            with self.subTest(item=item),self.assertRaises(ValueError):self.run_patch([item])
            self.assertEqual(self.state,original)
        self.state['storage']=[{'key':'item-2','count':5}]
        with self.assertRaises(ValueError):self.run_patch([{'op':'copy','from':'/items/"item-2"','path':'/storage'}])
        self.state['storage']=[]
        self.schema['properties']['storage']['items']['properties']['count']['type']='string'
        with self.assertRaises(ValidationError):self.run_patch([{'op':'copy','from':'/items/"item-2"','path':'/storage'}])

    def test_copy_cannot_append_into_a_collection_inside_its_source_element(self):
        schema=obj({'groups':{'type':'array','x-id-field':'key','items':obj({
            'key':{'type':'string'}, 'children':records()})}})
        state={'groups':[{'key':'group-a','children':[]}]}
        with self.assertRaisesRegex(ValueError,'outside its source element'):
            apply(state,[{'op':'copy','from':'/groups/"group-a"','path':'/groups/"group-a"/children'}],'value_patch',schema)

    def test_primitive_move_and_root_collection_append(self):
        schema=obj({'a':{'type':'array','items':{'type':'string'},'uniqueItems':True},
                    'b':{'type':'array','items':{'type':'string'},'uniqueItems':True}})
        self.assertEqual(apply({'a':['x/y','z'],'b':[]},[{'op':'move','from':'/a/"x/y"','path':'/b'}],'value_patch',schema),
                         {'a':['z'],'b':['x/y']})
        self.assertEqual(apply([], [{'op':'add','path':'','value':'x'}], 'value_patch',schema['properties']['a']),['x'])

    def test_detailed_and_summary_evaluators_agree_and_retain_failure_reasons(self):
        test={'id':'value-path-example','source':{'initial_state':self.state},'state_schema':self.schema,
              'expected_state':{**self.state,'items':[{'key':'item-7','count':1},{'key':'item-2','count':9}]}}
        variant={'id':'normal','result':{'step':'patch','representation':'value_patch','required_ops':['replace']}}
        for path,expected in (('/items/"item-2"/count','PASS'),('/items/1/count','FAIL'),('/items/"missing"/count','FAIL')):
            values={'patch':json.dumps([{'op':'replace','path':path,'value':9}])}
            self.assertEqual(assess(test,variant,values)['objective_outcome'],expected)
            self.assertEqual(evaluate(test,variant,values)['exact_match'],expected=='PASS')
            if expected=='FAIL':
                report=assess(test,variant,values)
                self.assertTrue(any('match exactly one' in c['explanation'] for c in report['checks']))
        self.assertFalse(score_state(test,'[{"op":"replace","path":"/items/1/count","value":9}]','value_patch')['valid'])

    def test_standard_json_patch_still_uses_indexes_and_standard_append(self):
        after=apply(self.state,[{'op':'replace','path':'/items/1/count','value':9}], 'json_patch')
        self.assertEqual(after['items'][1]['count'],9)
        with self.assertRaises(ValueError):
            apply(self.state,[{'op':'replace','path':'/items/"item-2"/count','value':9}], 'json_patch')
