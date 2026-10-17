import unittest
from workbench.seedcheck import run_seed_check

class FakeSeedBackend:
    def __init__(self,nondeterministic=False):
        self.nondeterministic=nondeterministic;self.count=0
    def clear_cache(self):pass
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        self.count+=1
        salt=self.count if self.nondeterministic else 0
        return {'text':f"story seed={settings['seed']} salt={salt}",'reasoning_text':'','finish_reason':'stop'}

class SeedCheckTests(unittest.TestCase):
    def test_same_seed_exact_and_different_seed_changes_output(self):
        result=run_seed_check(FakeSeedBackend())
        self.assertTrue(result['same_seed_exact_match'])
        self.assertTrue(result['different_seed_changes_output'])
        self.assertTrue(result['seed_behavior_verified'])
    def test_same_seed_mismatch_is_recorded_not_hidden(self):
        result=run_seed_check(FakeSeedBackend(True))
        self.assertFalse(result['same_seed_exact_match'])
        self.assertFalse(result['seed_behavior_verified'])
        self.assertEqual(result['status'],'completed')

if __name__=='__main__':unittest.main()
