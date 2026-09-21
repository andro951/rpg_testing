"""Authenticated loopback/private-Tailscale browser UI; no public bind or shell API."""
from __future__ import annotations
import functools
import hmac
import ipaddress
import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .controller import Controller
from .domain import TIERS, read_json, write_json, safe_id, validate_test
from .inventory import executable,command

class Forbidden(Exception):pass

class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,app,token):
        host=ipaddress.ip_address(address[0])
        if not host.is_loopback and host not in ipaddress.ip_network('100.64.0.0/10'):
            raise ValueError('Control server must bind to loopback or a Tailscale IPv4 address')
        self.app=app;self.token=token;self.remote_server=None;self.exit_requested=False;self.owner=self
        super().__init__(address,Handler)
    def enable_remote(self):
        if self.owner is not self:return self.owner.enable_remote()
        if self.app.operation.locked():raise RuntimeError('Wait until the current operation finishes.')
        if self.remote_server:return self.app.remote_info
        tailscale=executable('tailscale')
        if not tailscale:raise ValueError('Install and sign in to Tailscale first.')
        ip=command([tailscale,'ip','-4']).splitlines()[0].strip()
        if ipaddress.ip_address(ip) not in ipaddress.ip_network('100.64.0.0/10'):raise ValueError('Tailscale did not return a private tailnet IPv4 address')
        remote=WorkbenchServer((ip,self.server_port),self.app,self.token)
        self.remote_server=remote;remote.owner=self
        threading.Thread(target=remote.serve_forever,daemon=True).start()
        self.app.settings['remote_enabled']=True;self.app.save_settings()
        self.app.remote_info={'url':f'http://{ip}:{self.server_port}/','note':'Open this address on your laptop and enter the pairing key. Keep the desktop awake.'}
        self.app.log('network','Enabled private Tailscale controller at '+ip)
        return self.app.remote_info
    def disable_remote(self):
        if self.owner is not self:return self.owner.disable_remote()
        if self.remote_server:
            self.remote_server.shutdown();self.remote_server.server_close();self.remote_server=None
        self.app.settings['remote_enabled']=False;self.app.save_settings();self.app.remote_info=None
    def close_all(self):
        if self.owner is not self:return self.owner.close_all()
        if self.remote_server:
            self.remote_server.shutdown();self.remote_server.server_close()
        self.shutdown();self.server_close()

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def authorize(self):
        host=self.headers.get('Host','')
        allowed={f'{self.server.server_address[0]}:{self.server.server_port}'}
        if self.server.server_address[0]=='127.0.0.1':allowed.add(f'localhost:{self.server.server_port}')
        if host not in allowed:raise Forbidden('Unrecognized Host header')
        origin=self.headers.get('Origin')
        if origin is not None and origin!='http://'+host:raise Forbidden('Cross-origin requests are not allowed')
        auth=self.headers.get('Authorization','')
        if not hmac.compare_digest(auth,'Bearer '+self.server.token):raise Forbidden('Pair this browser with the worker first.')
    def send(self,status,data,kind='application/json; charset=utf-8',filename=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        try:
            url=urlsplit(self.path);path=url.path;q=parse_qs(url.query);app=self.server.app
            if path in ('/','/app.js','/style.css'):
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path]
                kind={'/':'text/html; charset=utf-8','/app.js':'application/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path]
                return self.send(200,(Path(__file__).parent/'web'/name).read_bytes(),kind)
            self.authorize()
            if path=='/api/state':return self.send(200,app.snapshot())
            if path=='/api/results':return self.send(200,app.result_records())
            if path=='/api/analysis':
                from .analysis import summarize
                return self.send(200,summarize(app.result_records()))
            if path=='/api/export':return self.send(200,app.export(),'application/zip','rpg-testing-evidence.zip')
            if path=='/api/tests':
                if app.operation.locked():raise RuntimeError('Wait until the operation finishes before reading test files.')
                return self.send(200,{'tests':[read_json(p) for p in sorted((app.root/'test_specs').glob('*.json'))],
                    'examples':[p.stem for p in sorted((app.root/'examples/test_specs').glob('*.json'))]})
            if path=='/api/browse':
                if app.operation.locked():raise RuntimeError('Wait until the operation finishes before browsing files.')
                p=Path(q.get('path',[str(Path.home())])[0]).expanduser().resolve()
                if not p.is_dir():raise ValueError('Folder not found')
                entries=[]
                for f in sorted(p.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower())):
                    if f.is_symlink() or f.name.startswith('.'):continue
                    try:
                        if f.is_dir() or f.suffix.lower() in ('.exe','.pem','.key','.pub') or f.name in ('lms','llama-server','id_ed25519','id_rsa'):
                            entries.append({'name':f.name,'path':str(f),'directory':f.is_dir()})
                    except OSError:continue
                roots=[f'{chr(d)}:/' for d in range(65,91) if Path(f'{chr(d)}:/').is_dir()] if os.name=='nt' else ['/']
                return self.send(200,{'path':str(p),'parent':str(p.parent),'entries':entries,'roots':roots})
            if path=='/api/pairing-key':
                if not ipaddress.ip_address(self.client_address[0]).is_loopback:raise Forbidden('Display the pairing key on the host computer.')
                return self.send(200,{'key':self.server.token})
            if path=='/api/unity-script':
                from .unity import make_script
                return self.send(200,make_script(q.get('tier',['16'])[0]).encode(),'text/plain; charset=utf-8','rpg-unity-job.sh')
            self.send(404,{'error':'Not found'})
        except Forbidden as exc:self.send(403,{'error':str(exc)})
        except (ValueError,KeyError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})
        except RuntimeError as exc:self.send(409,{'error':str(exc)})
        except Exception as exc:self.server.app.log('http_error',exc);self.send(500,{'error':'Internal error; inspect Logs.'})
    def do_POST(self):
        try:
            self.authorize();app=self.server.app;path=urlsplit(self.path).path
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Use application/json')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=16*1024**2:raise ValueError('Invalid request size')
            from .scoring import parse
            data=parse(self.rfile.read(size).decode()) if size else {}
            if not isinstance(data,dict):raise ValueError('Request body must be an object')
            if path=='/api/preflight':
                prep=data.get('preparation')
                if prep and (type(prep.get('vram_gb'))is not int or prep['vram_gb'] not in (*TIERS,11) or not isinstance(prep.get('gpu_name'),str)):raise ValueError('Invalid preparation GPU')
                app.start('preflight',data);return self.send(202,{'started':True})
            if path=='/api/run':app.start('run');return self.send(202,{'started':True})
            if path=='/api/fix':app.start('fix',data);return self.send(202,{'started':True})
            if path=='/api/control':app.control(data['action']);return self.send(200,{'ok':True})
            if path=='/api/settings':app.configure(data);return self.send(200,{'ok':True})
            if path=='/api/model/assign':app.assign_model(data['id'],data['required_vram_gb']);return self.send(200,{'ok':True})
            if path=='/api/result/delete':app.delete_result(data['model_id'],data['case_id']);return self.send(200,{'ok':True})
            if path=='/api/test/save':
                test=data['test'];validate_test(test)
                if not app.operation.acquire(blocking=False):raise RuntimeError('Wait until the active operation finishes.')
                try:write_json(app.root/'test_specs'/(safe_id(test['id'])+'.json'),test);app.report=None
                finally:app.operation.release()
                return self.send(200,{'ok':True})
            if path=='/api/test/import-example':
                name=safe_id(data['id']);source=app.root/'examples/test_specs'/(name+'.json')
                test=read_json(source);validate_test(test)
                if not app.operation.acquire(blocking=False):raise RuntimeError('Wait until the active operation finishes.')
                try:
                    target=app.root/'test_specs'/(name+'.json')
                    if target.exists():raise ValueError('This example is already installed; use its editor.')
                    write_json(target,test);app.report=None
                finally:app.operation.release()
                return self.send(200,{'ok':True})
            if path=='/api/remote/enable':return self.send(200,self.server.enable_remote())
            if path=='/api/remote/disable':
                if app.operation.locked():raise RuntimeError('Wait until the active operation finishes.')
                self.send(200,{'ok':True});threading.Thread(target=self.server.owner.disable_remote,daemon=True).start();return
            if path=='/api/shutdown':
                if app.operation.locked():raise RuntimeError('Stop the active operation before closing.')
                self.send(200,{'ok':True});threading.Thread(target=self.server.owner.close_all,daemon=True).start();return
            if path=='/api/restart':
                if app.operation.locked():raise RuntimeError('Stop the active operation before restarting.')
                self.server.owner.exit_requested=True;self.send(200,{'ok':True})
                threading.Thread(target=self.server.owner.close_all,daemon=True).start();return
            self.send(404,{'error':'Not found'})
        except Forbidden as exc:self.send(403,{'error':str(exc)})
        except (ValueError,KeyError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})
        except RuntimeError as exc:self.send(409,{'error':str(exc)})
        except Exception as exc:app.log('http_error',exc);self.send(500,{'error':'Internal error; inspect Logs.'})


def serve(root,demo=False,port=8765,open_browser=True):
    app=Controller(Path(root),demo=demo);keyfile=app.data/'control.key'
    if keyfile.exists():token=keyfile.read_text().strip()
    else:
        token=secrets.token_urlsafe(32);keyfile.write_text(token)
        try:os.chmod(keyfile,0o600)
        except OSError:pass
    server=WorkbenchServer(('127.0.0.1',port),app,token)
    if app.settings.get('remote_enabled'):
        try:server.enable_remote()
        except Exception as exc:app.log('network','Could not restore previously approved Tailscale binding: '+str(exc))
    if open_browser:webbrowser.open(f'http://127.0.0.1:{server.server_port}/#key={token}')
    try:server.serve_forever()
    finally:
        app.control('stop')
        if app.thread:app.thread.join(10)
        app.flush_logs();server.server_close()
    return 75 if server.exit_requested else 0
