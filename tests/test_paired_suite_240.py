"""Structural and reference checks; synthetic references are not inference results."""
import collections,json,unittest
from pathlib import Path
from prompt_builder.builder import load_case,applicable,validate_presentation_identity
from scripts.generate_paired_suite_240 import cases,ACTIONS,ROOT
class PairedSuite240Tests(unittest.TestCase):
 def test_exact_pairing_diversity_and_frozen_expected_states(self):
  groups=collections.defaultdict(list);states=set();originals=set()
  for name,s,action,patch,expected,text in cases():
   groups[name.split('__')[0]].append(action)
   states.add(json.dumps(s['state'],sort_keys=True,ensure_ascii=False))
   originals.update(s['originals'])
   c=load_case(name)
   self.assertEqual(c['starting_data'],s['state']);self.assertEqual(c['expected_result'],expected)
   self.assertEqual(c['expected_patch'],patch)
   self.assertEqual(c['requested_change'].strip(),text)
   if action=='no_op':self.assertEqual(expected,s['state'])
   else:self.assertNotEqual(expected,s['state'])
  self.assertEqual(len(groups),40);self.assertEqual(len(states),40);self.assertEqual(len(originals),21)
  for actions in groups.values():self.assertEqual(actions,list(ACTIONS))
 def test_original_21_requests_preserved(self):
  count=0
  for name,s,action,patch,expected,text in cases():
   for original in s['originals']:
    original_action='no_op' if original=='no_change' else original.split('_')[0]
    if original_action==action:
     p=ROOT/'archives/suite-before-240-2026-11-15/prompt_builder/templates/test_cases'/original/'requested_change.txt'
     self.assertEqual(text,p.read_text(encoding='utf-8').strip());count+=1
  self.assertEqual(count,21)
 def test_all_six_output_formats_are_representable(self):
  for name,*_ in cases():
   c=load_case(name)
   validate_presentation_identity(c,['normal_json','id_keyed_arrays','full_paths'])
   for fmt in ['json_dot','json_slash','path_list','literal_line','end_marked_line','typed_lines']:
    with self.subTest(case=name,format=fmt):self.assertIsNone(applicable(c,fmt))
if __name__=='__main__':unittest.main()
