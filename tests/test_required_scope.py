"""Historical fixed-schema scope remains an immutable evaluator regression."""
import copy,json,unittest
from pathlib import Path
from tests.helpers.frozen_prompts import INPUTS, definition, reference, snapshots
from workbench.domain import read_json
from workbench.scoring import apply
from workbench.workflows import evaluate
from evaluation.core import assess

class RequiredScopeTests(unittest.TestCase):
 def test_fixture_coverage_and_existing_oracles(self):
  selected=list(snapshots()['methods']['research_json_v2']);outside=set(snapshots()['methods']['dot_patch_v1'])-set(selected);self.assertEqual((len(selected),len(outside)),(13,8));count=0
  for f in selected:
   ops,expected=reference(f,'dot_patch_v1')
   for method in ('research_json_v2',):
    t=definition(f,method);self.assertEqual(t['expected_state'],expected)
    raw=json.dumps(ops)
    for v in t['variants']:
     self.assertTrue(evaluate(t,v,{'patch':raw})['exact_match']);self.assertEqual(assess(t,v,{'patch':raw})['objective_outcome'],'PASS');count+=1
  self.assertEqual(count,38)
 def test_old_field_value_contract_is_retired_not_reinterpreted(self):
  state={'items':[{'id':'a/b.c','n':1},{'id':'b','n':2}]};before=copy.deepcopy(state)
  for raw in ('none','set: items.a%2Fb%2Ec.n\nvalue: 9','remove: items.a%2Fb%2Ec'):
   with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'Retired response contract field_value_v2'):
    apply(state,raw,'field_value_v2',{})
  self.assertEqual(state,before)
 def test_dot_paths_presentations(self):
  for f in snapshots()['methods']['research_json_v2']:
   test=definition(f,'research_json_v2')
   for variant in test['variants']:
    self.assertIn('Separate path parts with dots',variant['prompt_bindings']['task_requirements'])
    if variant['id']=='full_paths':self.assertTrue(all(not line.startswith('/') for line in variant['prompt_bindings']['current_state'].splitlines()))

if __name__=='__main__':unittest.main()
