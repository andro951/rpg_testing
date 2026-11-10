"""Historical fixed-schema scope remains an immutable evaluator regression."""
import copy,json,unittest
from pathlib import Path
from tests.helpers.frozen_prompts import INPUTS, definition, reference, snapshots
from workbench.domain import read_json
from workbench.field_values import apply,decode
from workbench.workflows import evaluate
from evaluation.core import assess

class RequiredScopeTests(unittest.TestCase):
 def test_fixture_coverage_and_existing_oracles(self):
  selected=list(snapshots()['methods']['research_json_v2']);outside=set(snapshots()['methods']['dot_patch_v1'])-set(selected);self.assertEqual((len(selected),len(outside)),(13,8));count=0
  for f in selected:
   ops,expected=reference(f,'dot_patch_v1')
   for method in ('research_json_v2',):
    t=definition(f,method);self.assertEqual(t['expected_state'],expected)
    if method=='research_json_v2':raw=json.dumps(ops)
    else:
     from workbench.field_values import encode
     raw=encode(ops)
    for v in t['variants']:
     self.assertTrue(evaluate(t,v,{'patch':raw})['exact_match']);self.assertEqual(assess(t,v,{'patch':raw})['objective_outcome'],'PASS');count+=1
  self.assertEqual(count,38)
 def test_handwritten_unique_ids_and_real_deletion(self):
  schema={'type':'object','properties':{'items':{'type':'array','x-id-field':'id','items':{'type':'object','properties':{'id':{'type':'string'},'n':{'type':'integer'}},'required':['id','n'],'additionalProperties':False}}},'required':['items'],'additionalProperties':False}
  state={'items':[{'id':'a/b.c','n':1},{'id':'b','n':2}]};before=copy.deepcopy(state)
  self.assertEqual(apply(state,'set: items.a%2Fb%2Ec.n\nvalue: 9',schema)['items'][0]['n'],9)
  self.assertEqual(apply(state,'remove: items.a%2Fb%2Ec',schema),{'items':[{'id':'b','n':2}]})
  self.assertEqual(apply(state,'append: items\nvalue: {"id":"c","n":3}',schema)['items'][-1],{'id':'c','n':3})
  for raw in ('append: items\nvalue: {"id":"b","n":3}','remove: items.0','set: items.b.extra\nvalue: 3','append: items\nvalue: {"id":"c","id":"d","n":3}','remove: items.missing','remove: items.b\nvalue: null'):
   with self.subTest(raw=raw),self.assertRaises(Exception):apply(state,raw,schema)
  self.assertEqual(state,before);self.assertEqual(decode('none'),[])
 def test_dot_paths_presentations(self):
  for f in snapshots()['methods']['research_json_v2']:
   test=definition(f,'research_json_v2')
   for variant in test['variants']:
    self.assertIn('Separate path parts with dots',variant['prompt_bindings']['task_requirements'])
    if variant['id']=='full_paths':self.assertTrue(all(not line.startswith('/') for line in variant['prompt_bindings']['current_state'].splitlines()))
 def test_ambiguous_typed_ids_are_not_guessed(self):
  schema={'type':'object','properties':{'items':{'type':'array','items':{'type':['string','number']}}},'required':['items'],'additionalProperties':False}
  with self.assertRaisesRegex(ValueError,'Ambiguous'):apply({'items':[42,'42']},'remove: items.42',schema)

if __name__=='__main__':unittest.main()
