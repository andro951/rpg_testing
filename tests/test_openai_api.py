import unittest
from decimal import Decimal
from workbench.openai_api import PreparedOpenAIClient, prepare_scope, validate_scope, OpenAITransport

SCOPE=[{'id':'test','variants':[{'id':'off','retry_enabled':False},{'id':'on','retry_enabled':True,'retry_protocol':'justified-v2'}]}]
class Ledger:
    def __init__(self): self.calls=[]
    def reserve(self,*args,**kwargs): self.calls.append(('reserve',args,kwargs))
    def mark_unknown(self,*args,**kwargs): self.unknown=True
    def settle(self,*args,**kwargs): self.calls.append(('settle',args,kwargs)); return Decimal('.001')
class Transport:
    def __init__(self,response=None): self.calls=[]; self.response=response
    def request(self,*args):
        self.calls.append(args)
        if isinstance(self.response,Exception): raise self.response
        return self.response
class OpenAITest(unittest.TestCase):
    def client(self,response):
        self.ledger=Ledger(); self.transport=Transport(response)
        return PreparedOpenAIClient('gpt-6.1-sol','medium',self.ledger,self.transport,scope=SCOPE)
    def test_scope_rejects_legacy(self):
        old=[{'variants':[{'retry_enabled':True}]}]
        with self.assertRaises(ValueError):validate_scope(old)
        new=prepare_scope(old); self.assertEqual(validate_scope(new),1)
        self.assertNotIn('retry_protocol',old[0]['variants'][0])
    def test_response_metered_and_preserved(self):
        response={'status':'completed','usage':{'input_tokens':100,'output_tokens':20},'output':[{'type':'message','content':[{'type':'output_text','text':'[]'}]}]}
        client=self.client(response); got=client.generate([{'role':'user','content':'test'}])
        self.assertEqual(got['text'],'[]'); self.assertEqual(got['raw_response'],response)
        self.assertEqual([x[0] for x in self.ledger.calls],['reserve','settle'])
        request=self.transport.calls[0][2]
        self.assertNotIn('max_output_tokens',request); self.assertNotIn('temperature',request)
        self.assertEqual(request['service_tier'],'default'); self.assertFalse(request['store'])
    def test_uncertain_call_not_retried(self):
        client=self.client(TimeoutError())
        with self.assertRaises(TimeoutError):client.generate([{'role':'user','content':'test'}])
        with self.assertRaises(RuntimeError):client.generate([{'role':'user','content':'test'}])
        self.assertEqual(len(self.transport.calls),1); self.assertEqual(len(self.ledger.calls),1)
    def test_missing_usage_freezes(self):
        client=self.client({'status':'completed'})
        with self.assertRaises(RuntimeError):client.generate([{'role':'user','content':'test'}])
        self.assertTrue(client.failed)
    def test_no_arbitrary_endpoint(self):
        t=OpenAITransport('test')
        with self.assertRaises(ValueError):t.request('POST','https://example.com')
    def test_refuse_model_or_implicit_effort(self):
        for model,effort in [('gpt-6.1-luna','medium'),('gpt-6.1-sol',None)]:
            with self.assertRaises(ValueError):PreparedOpenAIClient(model,effort,Ledger(),Transport(),scope=SCOPE)
    def test_missing_usage_preserves_paid_response_and_request(self):
        raw = {'status':'completed', 'output':[{'type':'message','content':[{'type':'output_text','text':'paid answer'}]}]}
        client = self.client(raw)
        with self.assertRaises(RuntimeError) as caught:
            client.generate([{'role':'user','content':'original prompt'}])
        evidence = caught.exception.partial_response
        self.assertEqual(evidence['raw_response'], raw)
        self.assertEqual(evidence['request'], self.transport.calls[0][2])
        self.assertEqual(evidence['budget_call_id'], self.ledger.calls[0][1][0])
        self.assertTrue(self.ledger.unknown)
        self.assertTrue(client.failed)

    def test_settlement_overrun_preserves_response_without_masking_error(self):
        from workbench.api_budget import BudgetExceeded
        raw = {'status':'completed', 'usage':{'input_tokens':100,'output_tokens':20}}
        client = self.client(raw)
        def fail_settle(*args, **kwargs): raise BudgetExceeded('Observed bound overrun')
        def fail_unknown(*args, **kwargs): raise RuntimeError('Already settled')
        self.ledger.settle = fail_settle
        self.ledger.mark_unknown = fail_unknown
        with self.assertRaisesRegex(BudgetExceeded, 'Observed bound overrun') as caught:
            client.generate([{'role':'user','content':'test'}])
        self.assertEqual(caught.exception.partial_response['raw_response'], raw)
        self.assertEqual(caught.exception.partial_response['request'], self.transport.calls[0][2])
        self.assertEqual(caught.exception.partial_response['budget_call_id'], self.ledger.calls[0][1][0])
        self.assertTrue(client.failed)

    def test_transport_failure_still_preserves_request_and_call_id(self):
        client = self.client(TimeoutError('uncertain'))
        with self.assertRaises(TimeoutError) as caught:
            client.generate([{'role':'user','content':'test'}])
        evidence = caught.exception.partial_response
        self.assertIsNone(evidence['raw_response'])
        self.assertEqual(evidence['request'], self.transport.calls[0][2])
        self.assertEqual(evidence['budget_call_id'], self.ledger.calls[0][1][0])

    def test_failed_raw_sink_never_settles_or_makes_another_call(self):
        raw = {'status':'completed', 'usage':{'input_tokens':100,'output_tokens':20}}
        client = self.client(raw)
        def fail_sink(envelope): raise OSError('scripted disk failure')
        client.response_sink = fail_sink
        with self.assertRaises(OSError) as caught:
            client.generate([{'role':'user','content':'test'}])
        self.assertEqual(caught.exception.partial_response['raw_response'], raw)
        self.assertEqual([item[0] for item in self.ledger.calls], ['reserve'])
        self.assertTrue(self.ledger.unknown)
        with self.assertRaises(RuntimeError): client.generate([{'role':'user','content':'test'}])
        self.assertEqual(len(self.transport.calls), 1)

    def test_incomplete_preserved(self):
        client=self.client({'status':'incomplete','usage':{'input_tokens':100,'output_tokens':20}})
        with self.assertRaises(RuntimeError) as ctx:client.generate([{'role':'user','content':'test'}])
        self.assertEqual(ctx.exception.partial_response['raw_response']['status'],'incomplete')
        self.assertEqual(len(self.ledger.calls),2)
class WorkflowTest(unittest.TestCase):
    def test_new_review_feedback_is_cumulative(self):
        from workbench.openai_api import generate_condition
        class Client:
            failed=False
            def __init__(self):self.requests=[];self.responses=iter(['bad','No\nRight: source read. Wrong: update value.','fixed','Yes\nCorrect value and format.'])
            def generate(self,history):
                self.requests.append(history)
                return {'text':next(self.responses),'finish_reason':'stop'}
        client=Client();saved=[]
        got=generate_condition(client,[{'role':'user','content':'original'}],SCOPE[0]['variants'][1],persist_call=saved.append)
        self.assertEqual(len(saved),4);self.assertEqual(got['answer']['text'],'fixed')
        self.assertIn('Wrong: update value.',str(client.requests[2]))
        self.assertIn('natural-language justification',str(client.requests[1]))
    def test_off_has_single_call(self):
        from workbench.openai_api import generate_condition
        class Client:
            def generate(self,history):return {'text':'done','finish_reason':'stop'}
        saved=[];got=generate_condition(Client(),[{'role':'user','content':'original'}],{'retry_enabled':False},persist_call=saved.append)
        self.assertEqual(len(saved),1);self.assertIsNone(got['retry_protocol'])
    def test_legacy_never_calls(self):
        from workbench.openai_api import generate_condition
        with self.assertRaises(ValueError):generate_condition(None,[],{'retry_enabled':True},persist_call=lambda x:None)
if __name__=='__main__':unittest.main()
