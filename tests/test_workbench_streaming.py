"""Real local HTTP/SSE transport, plus isolated backend contract tests. No model weights."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from workbench.backends import Transport, BackendError
from workbench.native import NativeBackend
from workbench.execution_policy import ContextCapacity
from workbench.workflows import Cancelled, Unsupported

class Handler(BaseHTTPRequestHandler):
    mode='ok'
    request_body=None
    auth=None
    def log_message(self,*args):pass
    def do_POST(self):
        type(self).request_body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).auth=self.headers.get('Authorization')
        if self.mode=='http_error':self.send_response(503);self.end_headers();self.wfile.write(b'not ready');return
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        chunks=[{'choices':[{'delta':{'reasoning_content':'check'},'finish_reason':None}]},
                {'choices':[{'delta':{'content':'tr'},'finish_reason':None}]},
                {'choices':[{'delta':{'content':'ue'},'finish_reason':None}]}]
        if self.mode=='malformed':self.wfile.write(b'data: not json\n\n');return
        if self.mode=='error_event':self.wfile.write(b'data: {"error":"failed"}\n\n');return
        if self.mode!='no_finish':chunks.append({'choices':[{'delta':{},'finish_reason':'length' if self.mode=='length' else 'stop'}],
            'usage':{'prompt_tokens':20,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':12}},'timings':{'predicted_ms':12.5}})
        for chunk in chunks:self.wfile.write(b'data: '+json.dumps(chunk).encode()+b'\n\n')
        self.wfile.write(b'data: [DONE]\n\n')

class StreamingTests(unittest.TestCase):
    def setUp(self):
        Handler.mode='ok';self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.transport=Transport('http://127.0.0.1:'+str(self.server.server_port),'secret')
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
    def request(self):return self.transport.request('/v1/chat/completions',{'messages':[]},stream=True)
    def test_stream_keeps_text_reasoning_usage_separate(self):
        r=self.request();self.assertEqual(r['text'],'true');self.assertEqual(r['reasoning_text'],'check')
        self.assertEqual(r['cached_tokens'],12);self.assertEqual(r['usage']['completion_tokens'],3)
        self.assertEqual(r['finish_reason'],'stop');self.assertGreaterEqual(r['first_visible_text_seconds'],r['first_token_seconds'])
        self.assertEqual(Handler.auth,'Bearer secret');self.assertEqual(Handler.request_body,{'messages':[]})
    def test_http_error_not_wrong_answer(self):
        Handler.mode='http_error'
        with self.assertRaises(BackendError):self.request()
    def test_missing_finish_is_infrastructure_error(self):
        Handler.mode='no_finish'
        with self.assertRaises(BackendError):self.request()
    def test_malformed_stream_is_infrastructure_error(self):
        Handler.mode='malformed'
        with self.assertRaises(BackendError):self.request()
    def test_error_event(self):
        Handler.mode='error_event'
        with self.assertRaises(BackendError):self.request()
    def test_length_finish_preserved_not_hidden(self):
        Handler.mode='length';self.assertEqual(self.request()['finish_reason'],'length')
    def test_cancel_before_request(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):self.transport.request('/test',{},stream=True,cancel=cancel)
    def test_remote_inference_rejected(self):
        for u in ['http://100.64.0.1:1234','http://example.com','https://127.0.0.1','http://user:pass@localhost']:
            with self.assertRaises(ValueError):Transport(u)

class FakeTransport:
    def __init__(self):self.calls=[];self.token_count=8
    def request(self,path,body=None,**kwargs):
        self.calls.append((path,body,kwargs))
        if path=='/apply-template':return {'prompt':'formatted'}
        if path=='/tokenize':return {'tokens':[0]*self.token_count}
        if path.startswith('/slots/'):return {'n_erased':123}
        return {'text':'true','finish_reason':'stop','usage':{},'timings':{},'cached_tokens':0}

class AdapterTests(unittest.TestCase):
    def backend(self):
        b=NativeBackend({'backend':'llamacpp'},{'uuid':'GPU-test'});b.context=4096;b.owned_id='chosen-model';b.transport=FakeTransport();return b
    def test_native_no_arbitrary_output_limit(self):
        b=self.backend();b.generate([{'role':'user','content':'test'}],{'temperature':0,'seed':42},{'type':'boolean'})
        body=b.transport.calls[-1][1]
        self.assertEqual(body['max_tokens'],-1)
        self.assertEqual(body['response_format']['json_schema']['schema'],{'type':'boolean'})
        self.assertEqual(body['model'],'chosen-model')
    def test_native_unlimited_and_cache_off_erase(self):
        b=self.backend();r=b.generate([],{'temperature':0},None,'off')
        body=b.transport.calls[-1][1]
        self.assertEqual(body['max_tokens'],-1);self.assertFalse(body['cache_prompt'])
        self.assertIn('/slots/0?action=erase',[x[0] for x in b.transport.calls]);self.assertEqual(r['input_tokens_verified'],8)
    def test_native_cache_on(self):
        b=self.backend();b.generate([],{},None,'on')
        self.assertTrue(b.transport.calls[-1][1]['cache_prompt'])
    def test_removed_backend_is_not_selectable(self):
        with self.assertRaises(ValueError):NativeBackend({'backend':'lmstudio'},{})
    def test_native_input_exhaustion_no_generation(self):
        b=self.backend();b.transport.token_count=4096
        with self.assertRaises(ContextCapacity):b.generate([],{},None)
        self.assertNotIn('/v1/chat/completions',[x[0] for x in b.transport.calls])
    def test_missing_cache_reset_confirmation(self):
        b=self.backend();b.transport.request=lambda *a,**k:{}
        with self.assertRaises(Unsupported):b.clear_cache()
    def test_seed_and_temperature_are_per_request(self):
        b=self.backend()
        b.generate([],{'temperature':.8,'seed':7},None)
        b.generate([],{'temperature':0,'seed':7},None)
        requests=[x for x in b.transport.calls if x[0]=='/v1/chat/completions']
        self.assertEqual([x[1]['temperature'] for x in requests],[.8,0])
        self.assertEqual([x[1]['seed'] for x in requests],[7,7])
    def test_unload_without_owned_process_does_not_stop_external_server(self):
        b=self.backend();b.unload()
        self.assertEqual(b.transport.calls,[]);self.assertIsNone(b.owned_id)
if __name__=='__main__':unittest.main()
