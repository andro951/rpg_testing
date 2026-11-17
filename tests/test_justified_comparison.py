import copy
import unittest
from tests.test_self_review import fixture
from workbench.justified_comparison import prepare

class ComparisonTests(unittest.TestCase):
    def test_no_retry_excluded_and_original_inputs_controls_unchanged(self):
        t=fixture(); on=t['variants'][0]
        on['sampling']={'seed':42}; t['repetitions']=3
        off=copy.deepcopy(on); off.update(id='off', retry_enabled=False)
        omitted=copy.deepcopy(off); omitted['id']='omitted'; omitted.pop('retry_enabled')
        t['variants'] += [off,omitted]
        old=copy.deepcopy(t)
        selected,manifest=prepare([t])
        self.assertEqual(t,old)
        self.assertEqual(len(selected[0]['variants']),1)
        v=selected[0]['variants'][0]; self.assertEqual(v.pop('retry_protocol'),'justified-v2')
        self.assertEqual(v,on); self.assertEqual(selected[0]['repetitions'],3)
        self.assertEqual(selected[0]['source'],t['source'])
        self.assertEqual(manifest['affected_variants'],1)
        self.assertNotEqual(manifest['pairs'][0]['source_variant_sha256'],manifest['pairs'][0]['revised_variant_sha256'])
    def test_empty_or_already_revised_source_rejected(self):
        with self.assertRaises(ValueError): prepare([fixture(False)])
        t=fixture();t['variants'][0]['retry_protocol']='justified-v2'
        with self.assertRaises(ValueError):prepare([t])
    def test_disabled_and_duplicate_conditions_rejected(self):
        t=fixture(); t['enabled']=False
        with self.assertRaises(ValueError):prepare([t])
        t=fixture()
        with self.assertRaises(ValueError):prepare([t,t])

    def test_context_plans_actual_protocol_controls_without_extra_output_caps(self):
        from workbench.inventory import automatic_context
        t=fixture(); selected,_=prepare([t]); metadata={'model.context_length':32768}
        old=automatic_context([t],metadata); new=automatic_context(selected,metadata)
        self.assertGreater(new['review_control_estimate_bytes'],old['review_control_estimate_bytes'])
        self.assertEqual(new['input_estimate_bytes'],old['input_estimate_bytes'])
        self.assertEqual(new['continuation_history_headroom'],old['continuation_history_headroom'])
        self.assertIsNone(new['output_cap'])
