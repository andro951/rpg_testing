"""Local-only inference adapters. No remote model requests, implicit downloads, or file logs."""
from __future__ import annotations
import http.client
import json
import os
import re
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
        lower_event=event.lower()
        ticket_container=source.get('tickets')
        ticket_entries=(list(enumerate(ticket_container)) if isinstance(ticket_container,list)
                        else sorted(ticket_container.items(),key=lambda kv:int(kv[0])) if isinstance(ticket_container,dict)
                        else [])
        def ticket_key(ticket_id):
            for key,item in ticket_entries:
                if isinstance(item,dict) and item.get('ticket_id')==ticket_id:return str(key)
            return None
        ticket_ids=re.findall(r'SR-[0-9]+',event)
        is_coat_remove='takes off his coat and hangs it on the hook' in lower_event
        is_coat_add='brown leather coat is hanging' in lower_event and 'puts it on over his shirt' in lower_event
        is_time='minutes' in event and not is_inventory and not is_coat_remove and not is_coat_add
        if schema and schema.get('type')=='boolean':
            text='true' if ('time' in instruction.lower() and is_time) or 'correct' in instruction.lower() else 'false'
        elif schema and schema.get('type')=='string':text='"14:20"'
        elif 'Describe' in instruction:
            if is_inventory:text='On-hand inventory changes from 42 to 49 units. Product metadata, reservations, reorder point, units on order, backorder status, supplier, bin location, and lifecycle status do not change.'
            elif is_coat_remove:text="Evan removes the brown leather coat from his current clothing. His other tracked fields and Laura's state do not change."
            elif is_coat_add:text="Evan adds the brown leather coat to his current clothing. His other tracked fields and Laura's state do not change."
            else:text='The time changes to 14:20.' if is_time else 'Tom adds a green jacket and does not move.'
        elif 'narrat' in instruction.lower():text='Tom waits in the kitchen. Exactly five minutes pass. The clock now reads 14:20.'
        else:
            semantic='list_add' in instruction or 'semantic' in instruction
            if 'status is now resolved' in lower_event and ticket_ids:
                key=ticket_key(ticket_ids[0]);patch=[{'op':'replace','path':f'/tickets/{key}/status','value':'resolved'}]
            elif 'removed from the active support queue' in lower_event and ticket_ids:
                key=ticket_key(ticket_ids[0]);patch=[{'op':'remove','path':f'/tickets/{key}'}]
            elif 'inserted immediately before ticket' in lower_event:
                target=re.search(r'before ticket (SR-[0-9]+)',event,re.I);key=ticket_key(target.group(1)) if target else None
                patch=[{'op':'add','path':f'/tickets/{key}','value':{'ticket_id':'SR-99991','status':'open','priority':'urgent','subject':'VPN access failed after credential rotation','customer_contact':'new.user@example.test'}}]
            elif 'moved in the active queue' in lower_event and len(ticket_ids)>=2:
                source_key=ticket_key(ticket_ids[0]);dest_key=ticket_key(ticket_ids[1])
                patch=[{'op':'move','from':f'/tickets/{source_key}','path':f'/tickets/{dest_key}'}]
            elif 'copy the complete current record' in lower_event and ticket_ids:
                key=ticket_key(ticket_ids[0]);patch=[{'op':'copy','from':f'/tickets/{key}','path':'/review_samples/-'}]
            elif 'precondition test before the change' in lower_event and ticket_ids:
                key=ticket_key(ticket_ids[0]);patch=[{'op':'test','path':f'/tickets/{key}/status','value':'waiting_customer'},
                                                     {'op':'replace','path':f'/tickets/{key}/status','value':'active'}]
            elif is_inventory:patch=[{'op':'set' if semantic else 'replace','path':'/inventory/on_hand_units','value':49}]
            elif is_coat_remove:patch=([{'op':'list_remove','path':'/household/members/evan_harper/clothing','value':'brown leather coat'}] if semantic else [{'op':'remove','path':'/household/members/evan_harper/clothing/4'}])
            elif is_coat_add:patch=([{'op':'list_add','path':'/household/members/evan_harper/clothing','value':'brown leather coat'}] if semantic else [{'op':'add','path':'/household/members/evan_harper/clothing/-','value':'brown leather coat'}])
            elif is_time:patch=[{'op':'set' if semantic else 'replace','path':'/time','value':'14:20'}]
            else:patch=[{'op':'list_add' if semantic else 'add','path':'/characters/Tom/clothing'+('' if semantic else '/-'),'value':'green jacket'}]
            text=canonical(patch)
        return {'text':text,'finish_reason':'stop','request_seconds':.02,'first_token_seconds':.01,
                'usage':{},'timings':{},'cached_tokens':1024 if cache=='on' and self.counter>1 else 0,
                'simulated':True,'raw_chunks':[]}
