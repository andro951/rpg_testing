import copy
import json
import unittest

from prompt_builder.presentation import full_paths, keyed, render


class DeclaredIdentityViewsTests(unittest.TestCase):
    def test_nested_wildcards_use_exact_properties_and_preserve_all_data(self):
        data={'groups.list':[
            {'uid/key':'g.雪','id':'decoy','members':[
                {'':'member/%','other_id':'other','values':['',None,True,7,2.5,'a.b/雪'],'empty':[]}]},
            {'uid/key':'g2','id':'duplicate-decoy','members':[
                {'':'member/%','other_id':'other','values':['second'],'empty':[]}]}
        ]}
        declarations=[
            {'path':['groups.list'],'id_field':'uid/key'},
            {'path':['groups.list',None,'members'],'id_field':''},
            {'path':['groups.list',None,'members',None,'values'],'id_field':None},
            {'path':['groups.list',None,'members',None,'empty'],'id_field':'future sku'},
        ]
        original=copy.deepcopy((data,declarations))
        converted=keyed(data,declarations)
        groups=converted['$object']['groups.list']['$array']
        self.assertEqual(list(groups),['g.雪','g2'])
        member=groups['g.雪']['$object']['members']['$array']['member/%']['$object']
        self.assertEqual(member,{'':'member/%','other_id':'other',
            'values':{'$array':{'':'','null':None,'true':True,'7':7,'2.5':2.5,'a.b/雪':'a.b/雪'}},
            'empty':{'$array':{}}})
        self.assertEqual(groups['g2']['$object']['members']['$array']['member/%']['$object']['values'],
                         {'$array':{'second':'second'}})
        lines=full_paths(data,declarations)
        prefix='groups%2Elist.g%2E%E9%9B%AA.members.member%2F%25'
        self.assertIn(prefix+'.%_: "member/%"',lines)
        self.assertIn(prefix+'.other_id: "other"',lines)
        self.assertIn(prefix+'.values.%_: ""',lines)
        self.assertIn(prefix+'.values.null: null',lines)
        self.assertIn(prefix+'.values.true: true',lines)
        self.assertIn(prefix+'.values.7: 7',lines)
        self.assertIn(prefix+'.values.2%2E5: 2.5',lines)
        self.assertIn(prefix+'.values.a%2Eb%2F%E9%9B%AA: "a.b/雪"',lines)
        self.assertIn(prefix+'.empty: []',lines)
        self.assertEqual((data,declarations),original)

    def test_root_arrays_and_empty_containers(self):
        data=[{'sku':False,'id':'decoy','empty':{}},{'sku':None,'id':'decoy','empty':{}}]
        declarations=[{'path':[],'id_field':'sku'}]
        self.assertEqual(keyed(data,declarations),{'$array':{
            'false':{'$object':{'sku':False,'id':'decoy','empty':{'$object':{}}}},
            'null':{'$object':{'sku':None,'id':'decoy','empty':{'$object':{}}}}}})
        self.assertEqual(full_paths(data,declarations),[
            '<root>: <array>','false: <object>','false.sku: false','false.id: "decoy"','false.empty: {}',
            'null: <object>','null.sku: null','null.id: "decoy"','null.empty: {}'])
        for field in (None,'sku'):
            declarations=[{'path':[],'id_field':field}]
            self.assertEqual(keyed([],declarations),{'$array':{}})
            self.assertEqual(full_paths([],declarations),['<root>: []'])
        self.assertEqual(keyed({},[]),{'$object':{}})
        self.assertEqual(full_paths({},[]),['<root>: {}'])
        self.assertEqual(keyed('scalar',[]),'scalar')
        self.assertEqual(full_paths('scalar',[]),['<root>: "scalar"'])

    def test_empty_nested_array_declarations_do_not_supply_values_or_schema_text(self):
        data={'records':[]}
        base=[{'path':['records'],'id_field':'sku'}]
        hidden=base+[{'path':['records',None,'HIDDEN_COLLECTION'],'id_field':'HIDDEN_FIELD'}]
        for mode in ('id_keyed_arrays','full_paths'):
            self.assertEqual(render(data,mode,base),render(data,mode,hidden))
            self.assertNotIn('HIDDEN',render(data,mode,hidden))

    def test_conversions_require_explicit_mapping_even_for_empty_or_scalar_input(self):
        for data in ({'records':[{'id':'a'}]},{'records':[]},[],{},'scalar'):
            for mode in ('id_keyed_arrays','full_paths'):
                with self.subTest(data=data,mode=mode):
                    with self.assertRaisesRegex(ValueError,'explicit list'):
                        render(data,mode)
        with self.assertRaisesRegex(ValueError,'explicit list'):keyed([])
        with self.assertRaisesRegex(ValueError,'explicit list'):full_paths([])

    def test_invalid_declarations_and_missing_paths_never_fall_back_to_id_names(self):
        data={'records':[{'id':'a','sku':'b'}]}
        mapping={'path':['records'],'id_field':'sku'}
        cases=[
            ({},'explicit list'),
            ([], 'Missing array identity mapping'),
            ([{'path':['records']}], 'requires only path and id_field'),
            ([{**mapping,'schema':{}}], 'requires only path and id_field'),
            ([{**mapping,'id_field':42}], 'id_field must be'),
            ([{**mapping,'path':'records'}], 'path must be'),
            ([{**mapping,'path':['records',0]}], 'path must be'),
            ([mapping,mapping], 'Duplicate array identity path'),
            ([{'path':['records',None,'children'],'id_field':'id'}], 'Missing parent array identity'),
            ([{**mapping,'id_field':None},{'path':['records',None,'children'],'id_field':'id'}],
             'Primitive identity array cannot contain nested collections'),
            ([{**mapping,'id_field':'missing'}], 'Object identity requires scalar field'),
            ([{**mapping,'id_field':None}], 'Primitive identity mapping cannot select container'),
            ([mapping,{'path':['missing'],'id_field':'id'}], 'has no matching collection'),
            ([mapping,{'path':['records',None,'sku'],'id_field':'id'}], 'targets a non-array'),
        ]
        for declarations,error in cases:
            for mode in ('id_keyed_arrays','full_paths'):
                with self.subTest(declarations=declarations,mode=mode):
                    with self.assertRaisesRegex(ValueError,error):render(data,mode,declarations)

    def test_selected_identity_must_be_present_scalar_unique_and_unambiguous(self):
        cases=[
            ([{'id':'a','sku':'x'},{'id':'b'}],'sku','scalar field'),
            ([{'id':'a','sku':{}},{'id':'b','sku':[]}],'sku','scalar field'),
            ([{'id':'a','sku':'x'},{'id':'b','sku':'x'}],'sku','Duplicate collection identifiers'),
            ([{'id':'a','sku':1},{'id':'b','sku':1.0}],'sku','Duplicate collection identifiers'),
            ([{'id':'a','sku':1},{'id':'b','sku':'1'}],'sku','Ambiguous plain selectors'),
            ([{'id':'a','sku':None},{'id':'b','sku':'null'}],'sku','Ambiguous plain selectors'),
            (['a','a'],None,'Duplicate collection identifiers'),
            ([False,'false'],None,'Ambiguous plain selectors'),
            ([{'id':'a'},'b'],'id','scalar field'),
            ([[]],None,'cannot select container'),
        ]
        for data,field,error in cases:
            declarations=[{'path':[],'id_field':field}]
            for mode in ('id_keyed_arrays','full_paths'):
                with self.subTest(data=data,field=field,mode=mode):
                    with self.assertRaisesRegex(ValueError,error):render(data,mode,declarations)

    def test_every_empty_array_requires_its_own_mapping(self):
        data={'groups':[{'sku':'g','members':[]}]}
        declarations=[{'path':['groups'],'id_field':'sku'}]
        for mode in ('id_keyed_arrays','full_paths'):
            with self.assertRaisesRegex(ValueError,'Missing array identity mapping'):
                render(data,mode,declarations)
        declarations.append({'path':['groups',None,'members'],'id_field':'member code'})
        self.assertEqual(keyed(data,declarations)['$object']['groups']['$array']['g']['$object']['members'],{'$array':{}})
        self.assertIn('groups.g.members: []',full_paths(data,declarations))

    def test_nonconverted_rendering_ignores_even_malformed_metadata(self):
        data={'records':[{'id':'a','count':2}]}
        for mode in ('normal_json','named_tables'):
            expected=render(data,mode)
            for declarations in ({'schema':'INVALID'},[],[{'malformed':True}]):
                self.assertEqual(expected,render(data,mode,declarations))
        self.assertEqual(json.loads(render(data,'normal_json')),data)


if __name__=='__main__':unittest.main()
