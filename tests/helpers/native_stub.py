"""Subprocess integration fixture, NOT a model or GPU measurement."""
import argparse,json,os,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--alias');p.add_argument('--ctx-size',type=int);args=p.parse_args()
print('offloaded '+os.environ.get('STUB_LAYERS','33/33')+' layers to GPU',flush=True)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,body):self.send_response(200);self.end_headers();self.wfile.write(json.dumps(body).encode())
 def do_GET(self):
  if self.path=='/health':self.send({'status':'ok'})
  elif self.path=='/v1/models':self.send({'data':[{'id':args.alias}]})
  elif self.path=='/props':self.send({'default_generation_settings':{'n_ctx':args.ctx_size}})
  else:self.send_error(404)
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path=='/apply-template':self.send({'prompt':'test'})
  elif self.path=='/tokenize':self.send({'tokens':[1,2]})
  elif self.path.startswith('/slots/0'):self.send({'n_erased':0})
  elif self.path=='/v1/chat/completions':
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
   messages=str(body.get('messages'))
   if 'READY' in messages:content='Ready.'
   elif 'SEED_REPRODUCIBILITY_CHECK' in messages:
    seed=body.get('seed',-1)
    content=('At Observatory '+str(seed)+', Mara found a sealed metal box beneath the broken telescope. '
             'Wind pushed dust across the floor while she studied symbols scratched into its lid. '
             'Before she touched the latch, an unexpected visitor named Ivo stepped from the stairwell. '
             'He claimed the box had been waiting for someone who would choose not to open it. '
             'Mara carried it outside unopened, and the dead observatory lights flickered behind them.')
   else:content='[]'
   if 'WAIT_FOREVER' in str(body):time.sleep(10)
   chunks=[{'choices':[{'delta':{'content':content},'finish_reason':None}]},{'choices':[{'delta':{},'finish_reason':'stop'}]}]
   try:
    for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
    self.wfile.write(b'data: [DONE]\n\n')
   except (OSError,BrokenPipeError):pass
  else:self.send_error(404)
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
