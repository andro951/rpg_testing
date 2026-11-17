"""Isolated OpenAI preparation. Not registered with the controller or auto-launched.

Only synthetic text, explicit model/effort/budget and justified-v2 scopes. No
implicit retries, redirects, credential persistence, or hidden output truncation.
"""
from __future__ import annotations
import copy
import http.client
import json
import time
import uuid
from decimal import Decimal
from .api_budget import Prices
from .self_review import enabled, protocol, JUSTIFIED_PROTOCOL

MODELS = {'gpt-6.1-sol': ('2', '.10', '10'), 'gpt-6-luna': ('.10', '.01', '.50')}


def prepare_scope(tests):
    """Copy full suite, retaining off controls, changing every on case to v2."""
    out = copy.deepcopy(tests)
    for test in out:
        for variant in test['variants']:
            if enabled(variant):
                variant['retry_protocol'] = JUSTIFIED_PROTOCOL
    return out


def validate_scope(tests):
    count = 0
    for test in tests:
        if not test.get('enabled', True): continue
        for variant in test['variants']:
            if not variant.get('enabled', True): continue
            if enabled(variant) and protocol(variant) != JUSTIFIED_PROTOCOL:
                raise ValueError('OpenAI review runs require justified-v2')
            count += 1
    if not count: raise ValueError('Empty scope')
    return count


class OpenAITransport:
    """Single official HTTPS host, no redirects or retry of uncertain requests."""
    def __init__(self, api_key, timeout=120):
        if not api_key: raise ValueError('An authorized OpenAI API key is required')
        self._key = api_key
        self.timeout = timeout

    def request(self, method, path, body=None):
        if (method,path) not in {('GET','/v1/models'), ('POST','/v1/responses')}:
            raise ValueError('Unsupported endpoint')
        conn = http.client.HTTPSConnection('api.openai.com', timeout=self.timeout)
        try:
            conn.request(method,path,None if body is None else json.dumps(body).encode(),
                         {'Authorization':'Bearer '+self._key,'Content-Type':'application/json'})
            response = conn.getresponse()
            raw = response.read()
            if response.status != 200:
                # Do not echo arbitrary remote body, headers, credentials or request text.
                raise RuntimeError('OpenAI HTTP '+str(response.status)+'; no automatic retry')
            return json.loads(raw)
        finally:
            conn.close()

    def available_models(self):
        return sorted(row['id'] for row in self.request('GET','/v1/models')['data'])


class PreparedOpenAIClient:
    """Low-level client; not a drop-in native backend (controls differ).

    Caller must persist returned raw evidence via ResultStore/controller. Any
    uncertain request freezes this object; budget reservation remains durable.
    """
    def __init__(self, model, effort, ledger, transport, *, scope, response_sink=None):
        if model not in MODELS: raise ValueError('Unapproved model')
        if effort not in ('low','medium','high','xhigh','max'):
            raise ValueError('Explicit supported reasoning effort required')
        validate_scope(scope)
        self.model,self.effort,self.ledger,self.transport=model,effort,ledger,transport
        self.failed=False
        self.response_sink=response_sink

    def generate(self, messages):
        if self.failed: raise RuntimeError('Unreconciled prior request; cannot continue')
        if not isinstance(messages,list) or not messages: raise ValueError('Messages required')
        for message in messages:
            if message.get('role') not in ('system','developer','user','assistant') or not isinstance(message.get('content'),str):
                raise ValueError('Only plain-text conversation messages supported')
        inp,cached,out = map(Decimal,MODELS[self.model])
        short = Prices(inp,cached,out)
        long = Prices(inp*2,cached*2,out*Decimal('1.5'))
        call_id = uuid.uuid4().hex
        # Reserve model-native ceilings, not a new experimental output limit.
        self.ledger.reserve(call_id,1050000,128000,prices=long,
                            max_cost_usd=(Decimal(1050000)*long.input_per_million*Decimal('1.25')
                                          +Decimal(128000)*long.output_per_million)/Decimal(1000000))
        request={'model':self.model,'input':copy.deepcopy(messages),
                 'reasoning':{'effort':self.effort}, 'service_tier':'default','store':False,
                 'prompt_cache_options':{'mode':'implicit','ttl':'30m'}}
        started=time.perf_counter()
        settled=False
        response=None
        try:
            response=self.transport.request('POST','/v1/responses',request)
            if self.response_sink:
                self.response_sink({'raw_response':copy.deepcopy(response),'budget_call_id':call_id,
                                    'request':copy.deepcopy(request)})
            usage=response.get('usage')
            if not isinstance(usage,dict): raise RuntimeError('Missing billed token usage')
            cost=self.ledger.settle(call_id,usage,prices=long if usage.get('input_tokens',0)>272000 else short)
            settled=True
            if response.get('status')!='completed':
                exc=RuntimeError('Noncompleted OpenAI response; retain as infrastructure evidence')
                exc.partial_response=response
                raise exc
            text=''.join(part.get('text','') for item in response.get('output',[]) if item.get('type')=='message'
                         for part in item.get('content',[]) if part.get('type')=='output_text')
            return {'text':text,'raw_response':response,'request':request,'usage':usage,
                    'cost_usd':str(cost),'budget_call_id':call_id,'request_seconds':time.perf_counter()-started,
                    'finish_reason':'stop','provider':'openai','reasoning_effort':self.effort,
                    'output_limit_policy':'provider-native limit; no custom cap',
                    'unsupported_controls':['seed','top_k','min_p','cache_erasure','native_context_14336'],
                    'sampling_policy':'provider defaults; no unsupported native knobs sent'}
        except Exception as exc:
            exc.partial_response={'raw_response':copy.deepcopy(response),
                                  'budget_call_id':call_id,'request':copy.deepcopy(request),
                                  'incomplete':True}
            if not settled:
                try:self.ledger.mark_unknown(call_id, 'Request or billing evidence uncertain')
                except Exception:pass  # A settled overrun already durably halts its ledger.
            self.failed=True
            raise


def generate_condition(client, prompt, variant, *, persist_call, cancel=None):
    """Shared review engine adapter; persist every paid call before the next call.

    This is inference orchestration only, not scoring or ResultStore replacement.
    The caller supplies a durable raw-call sink and owns experiment identity,
    terminal-case save, result sync and resume. No legacy protocol accepted.
    """
    from . import self_review
    from .workflows import Cancelled
    if not callable(persist_call): raise ValueError('Durable raw-call sink required')
    on = enabled(variant)
    if on and protocol(variant) != JUSTIFIED_PROTOCOL:
        raise ValueError('Legacy GPT review forbidden')
    calls,events=[],[]
    def request(history, schema):
        if schema is not None: raise ValueError('Schema-constrained API control not validated')
        if cancel and cancel.is_set(): raise Cancelled('Stopped before API request')
        try:
            response=client.generate(history)
        except Exception as exc:
            persist_call({'incomplete':True,'request_messages':copy.deepcopy(history),
                          'raw_response':copy.deepcopy(getattr(exc,'partial_response',None)),
                          'request_error':type(exc).__name__})
            raise
        try: persist_call(copy.deepcopy(response))
        except Exception:
            client.failed=True
            raise
        return response
    if on:
        answer=self_review.generate(prompt,None,request,calls,events,{'step':'answer'},
                                    cancel=cancel,review_protocol=JUSTIFIED_PROTOCOL)
    else:
        answer=request(prompt,None)
        calls.append({**answer,'call_kind':'initial_answer','answer_attempt':0,'messages':copy.deepcopy(prompt)})
    return {'answer':answer,'calls':calls,'events':events,'retry_protocol':JUSTIFIED_PROTOCOL if on else None}
