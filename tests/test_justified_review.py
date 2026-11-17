"""Offline tests of opt-in review; no inference or active experiment changes."""
import unittest
from workbench import domain, perchance
from workbench.workflows import execute
from workbench.self_review import justified_decision, JUSTIFIED_PROTOCOL
from tests.test_self_review import fixture, Scripted

class JustifiedReviewTests(unittest.TestCase):
    def variant(self):
        t = fixture(); v=t['variants'][0]; v['retry_protocol']=JUSTIFIED_PROTOCOL
        return t,v
    def test_explicit_verdict_and_required_justification(self):
        for raw, expected in [('Yes\nThe requested answer is READY.', 'yes'),
                              ('No.\nRight: format. Wrong: value.', 'no'),
                              ('yes','ambiguous'), ('no\n  ','ambiguous'),
                              ('yes no\nReason','ambiguous'), ('yes\n...','ambiguous')]:
            self.assertEqual(justified_decision(raw),expected)
    def test_yes_reason_is_saved_and_no_retry(self):
        t,v=self.variant(); b=Scripted(['READY','Yes\nThe answer matches the request.'])
        r=execute(t,v,b)
        self.assertEqual(len(r['calls']),2)
        self.assertEqual(r['calls'][-1]['review_protocol'],JUSTIFIED_PROTOCOL)
        self.assertEqual(r['step_events'][0]['outcome'],'accepted')
    def test_no_feedback_is_in_replacement_context_both_providers(self):
        import threading
        for remote in (False,True):
            t,v=self.variant(); critique='No\nRight: plain text. Wrong: not READY.'
            b=Scripted(['WRONG',critique,'READY','Yes\nIt is READY.'],remote=remote)
            r=(perchance.execute_job({'test':t,'variant':v},b,threading.Event())
               if remote else execute(t,v,b))
            self.assertEqual(b.requests[2][0][-2]['content'],critique)
            self.assertIn('Use your review above',b.requests[2][0][-1]['content'])
            self.assertNotIn('secret_oracle',str(b.requests))
            self.assertTrue(r['score']['exact_match'])
    def test_identity_separate_and_invalid_protocol_rejected(self):
        t,v=self.variant(); old=dict(v); old.pop('retry_protocol')
        self.assertNotEqual(domain.experiment_spec(t,v),domain.experiment_spec(t,old))
        self.assertNotEqual(perchance.effective(t,v),perchance.effective(t,old))
        v['retry_protocol']='wrong'
        with self.assertRaises(ValueError): domain.validate_test(t)
    def test_grading_alias_is_exact_and_does_not_alias_workflow(self):
        from unittest.mock import patch
        from evaluation import array_identities_intent as evaluator
        info=evaluator.identity_info()
        self.assertEqual(info['fingerprint'],
                         'c71db6accfac0cfb6f5f40d3e42b541670f89d233b471da3ee5fddd4ed56e5ce')
        self.assertNotEqual(info['implementation_fingerprint'],info['fingerprint'])
        with patch.object(evaluator,'digest',return_value='f'*64):
            self.assertEqual(evaluator.configuration()['fingerprint'],'f'*64)
        self.assertEqual(domain.code_fingerprint(),domain.implementation_fingerprint())

    def test_retry_bound(self):
        t,v=self.variant(); b=Scripted(['wrong','No\nNothing right; wrong answer.']*4)
        r=execute(t,v,b)
        self.assertEqual(len(r['calls']),8)
        self.assertEqual(r['step_events'][-2]['outcome'],'retry_budget_exhausted')

if __name__=='__main__': unittest.main()
