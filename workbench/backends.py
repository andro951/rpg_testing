"""Local-only inference adapters. No remote model requests, implicit downloads, or file logs."""
from __future__ import annotations
import http.client
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from .domain import canonical
from .workflows import Cancelled, Unsupported

class BackendError(RuntimeError):
    pass

class Transport:
    def __init__(self, base_url: str, token: str = '', timeout: float = 900):
        url=urlsplit(base_url)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.username or url.password:
            raise ValueError('Inference must use an HTTP loopback endpoint on the GPU machine')
        self.host,self.port=url.hostname,url.port or 80
        self.token,self.timeout=token,timeout
        self.connection=None
    def cancel(self):
        conn=self.connection
        if conn:
            try:
                if conn.sock:conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            conn.close()
    def request(self,path,body=None,stream=False,cancel=None):
        conn=http.client.HTTPConnection(self.host,self.port,timeout=self.timeout)
        self.connection=conn
        headers={'Content-Type':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        started=time.perf_counter()
        chunks=[];text=[];reasoning=[];finish=None;usage={};timings={};first=None;visible=None
        def partial():
            return {'text':''.join(text),'reasoning_text':''.join(reasoning),'raw_chunks':chunks,
                    'finish_reason':finish,'usage':usage,'timings':timings,'incomplete':True,
                    'request_seconds':time.perf_counter()-started}
        try:
            if cancel and cancel.is_set():raise Cancelled('Cancelled')
            conn.request('POST' if body is not None else 'GET',path,canonical(body).encode() if body is not None else None,headers)
            response=conn.getresponse()
            if response.status>=400:
                detail=response.read(65536).decode('utf-8',errors='replace')
                raise BackendError(f'HTTP {response.status}: {detail}')
            if not stream:return json.loads(response.read())
            chunks=[];text=[];reasoning=[];finish=None;usage={};timings={};first=None;visible=None
            while True:
                if cancel and cancel.is_set():raise Cancelled('Cancelled')
                line=response.readline()
                if not line:
                    if cancel and cancel.is_set():raise Cancelled('Cancelled')
                    break
                if not line.startswith(b'data:'):continue
                data=line[5:].strip()
                if data==b'[DONE]':break
                chunk=json.loads(data);chunks.append(chunk)
                if 'error' in chunk:raise BackendError(str(chunk['error']))
                if chunk.get('usage'):usage=chunk['usage']
                if chunk.get('timings'):timings=chunk['timings']
                for choice in chunk.get('choices',[]):
                    delta=choice.get('delta',{})
                    piece=delta.get('content') or ''
                    thought=delta.get('reasoning_content') or delta.get('reasoning') or ''
                    if piece or thought:
                        if first is None:first=time.perf_counter()-started
                    if piece:
                        if visible is None:visible=time.perf_counter()-started
                        text.append(piece)
                    if thought:reasoning.append(thought)
                    if choice.get('finish_reason') is not None:finish=choice['finish_reason']
            if finish is None:raise BackendError('Stream ended without a finish reason')
            cached=usage.get('prompt_tokens_details',{}).get('cached_tokens',timings.get('cache_n'))
            return {'text':''.join(text),'reasoning_text':''.join(reasoning),'finish_reason':finish,
                    'request_seconds':time.perf_counter()-started,'first_token_seconds':first,
                    'first_visible_text_seconds':visible,'usage':usage,'timings':timings,
                    'cached_tokens':cached,'raw_chunks':chunks}
        except Exception as exc:
            error=Cancelled('Cancelled') if cancel and cancel.is_set() else exc if isinstance(exc,(Cancelled,BackendError)) else BackendError(str(exc))
            error.partial_response=partial()
            raise error from exc
        finally:
            conn.close();self.connection=None

class DemoBackend:
    """Plumbing only, prominently labelled simulated; never research evidence."""
    supports_cache=True
    supports_schema=True
    def __init__(self,log=lambda *args:None):self.log=log;self.counter=0;self.load_metadata={};self.context=65536
    def load(self,model,context,cancel=None):
        self.counter=0;self.load_metadata={'simulated':True,'context':context,'load_seconds':0.0,'health_exact_ready':True}
        return self.load_metadata
    def unload(self):pass
    def cancel(self):pass
    def clear_cache(self):self.counter=0
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        from .scoring import parse
        if cancel and cancel.is_set():raise Cancelled('Cancelled')
        time.sleep(.02)
        self.counter+=1
        source=parse(messages[1]['content'].split('\nSOURCE\n',1)[1])
        instruction=messages[-1]['content'];event=source.get('new_information','')
        is_inventory='A2667' in event and 'received' in event.lower() and 'shipped' in event.lower()
        is_time='minutes' in event and not is_inventory
        if schema and schema.get('type')=='boolean':
            text='true' if ('time' in instruction.lower() and is_time) or 'correct' in instruction.lower() else 'false'
        elif schema and schema.get('type')=='string':text='"14:20"'
        elif 'Describe' in instruction:
            text='On-hand inventory changes from 42 to 49 units. Product metadata, reservations, reorder point, units on order, backorder status, supplier, bin location, and lifecycle status do not change.' if is_inventory else ('The time changes to 14:20.' if is_time else 'Tom adds a green jacket and does not move.')
        elif 'narrat' in instruction.lower():text='Tom waits in the kitchen. Exactly five minutes pass. The clock now reads 14:20.'
        else:
            semantic='list_add' in instruction or 'semantic' in instruction
            patch=([{'op':'set' if semantic else 'replace','path':'/inventory/on_hand_units','value':49}] if is_inventory else ([{'op':'set' if semantic else 'replace','path':'/time','value':'14:20'}] if is_time else [{'op':'list_add' if semantic else 'add','path':'/characters/Tom/clothing'+('' if semantic else '/-'),'value':'green jacket'}]))
            text=canonical(patch)
        return {'text':text,'finish_reason':'stop','request_seconds':.02,'first_token_seconds':.01,
                'usage':{},'timings':{},'cached_tokens':1024 if cache=='on' and self.counter>1 else 0,
                'simulated':True,'raw_chunks':[]}
