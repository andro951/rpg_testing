"""Native-interface test double. Never evidence of model quality or GPU performance."""
import contextlib
import re
from .backends import DemoBackend
from .domain import canonical

class DemoNative(DemoBackend):
    def __init__(self,settings=None,gpu=None,log=lambda *a:None):super().__init__(log)
    def load(self,model,context,cancel=None,layers='all',execution_class='full_gpu'):
        super().load(model,context,cancel)
        self.load_metadata.update(placement={'status':execution_class,'gpu_layers':33 if layers=='all' else layers,
                                            'total_layers':33,'cpu_layers':0 if layers=='all' else 33-layers},
                                  execution_class=execution_class)
        return self.load_metadata
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        joined='\n'.join(m.get('content','') for m in messages)
        is_full_path=bool(re.search(r'(?m)^(?:tickets\.\d+|characters\.|household\.|product\.|inventory\.|time:|location:)',joined))
        if not is_full_path:return super().generate(messages,settings,schema,cache,cancel)
        self.counter+=1
        lower=joined.lower()
        def index(ticket_id):
            m=re.search(r'(?m)^tickets\.(\d+)\.ticket_id:\s*'+re.escape(ticket_id)+r'\s*$',joined)
            return m.group(1) if m else None
        is_inventory='a2667' in lower and 'received' in lower and 'shipped' in lower
        is_coat_remove='takes off his coat and hangs it on the hook' in lower
        is_coat_add='brown leather coat is hanging' in lower and 'puts it on over his shirt' in lower
        is_time='exactly five minutes pass' in lower
        is_unlock='tom unlocks the front door' in lower
        is_relaxed='tom is now relaxed' in lower
        analysis=('describe the established state changes' in lower or
                  'briefly tell me what needs to change' in lower or
                  'identify only state fields' in lower)
        if analysis:
            if is_inventory:text='On-hand inventory changes from 42 to 49 units. Product metadata, reservations, reorder point, units on order, backorder status, supplier, bin location, and lifecycle status do not change.'
            elif is_coat_remove:text="Evan removes the brown leather coat from his current clothing. His other tracked fields and Laura's state do not change."
            elif is_coat_add:text="Evan adds the brown leather coat to his current clothing. His other tracked fields and Laura's state do not change."
            elif is_time:text='The time changes to 14:20.'
            elif is_unlock:text='The front door becomes unlocked.'
            elif is_relaxed:text='Tom becomes relaxed.'
            else:text='Tom adds a green jacket and does not move.'
        else:
            semantic='semantic operations' in lower or 'small list of operations' in lower
            if 'status is now resolved' in lower:
                patch=[{'op':'replace','path':f'/tickets/{index("SR-60432")}/status','value':'resolved'}]
            elif 'removed from the active support queue' in lower:
                patch=[{'op':'remove','path':f'/tickets/{index("SR-81298")}'}]
            elif 'inserted immediately before ticket sr-79161' in lower:
                patch=[{'op':'add','path':f'/tickets/{index("SR-79161")}','value':{'ticket_id':'SR-99991','status':'open','priority':'urgent','subject':'VPN access failed after credential rotation','customer_contact':'new.user@example.test'}}]
            elif 'moved in the active support queue' in lower:
                patch=[{'op':'move','from':f'/tickets/{index("SR-22974")}','path':f'/tickets/{index("SR-77778")}'}]
            elif 'copy the complete current record' in lower:
                patch=[{'op':'copy','from':f'/tickets/{index("SR-63323")}','path':'/review_samples/-'}]
            elif 'precondition test before the change' in lower or ('sr-57541' in lower and 'active' in lower):
                key=index('SR-57541');patch=[{'op':'test','path':f'/tickets/{key}/status','value':'waiting_customer'},{'op':'replace','path':f'/tickets/{key}/status','value':'active'}]
            elif is_inventory:patch=[{'op':'set' if semantic else 'replace','path':'/inventory/on_hand_units','value':49}]
            elif is_coat_remove:patch=([{'op':'list_remove','path':'/household/members/evan_harper/clothing','value':'brown leather coat'}] if semantic else [{'op':'remove','path':'/household/members/evan_harper/clothing/4'}])
            elif is_coat_add:patch=([{'op':'list_add','path':'/household/members/evan_harper/clothing','value':'brown leather coat'}] if semantic else [{'op':'add','path':'/household/members/evan_harper/clothing/-','value':'brown leather coat'}])
            elif is_unlock:patch=[{'op':'replace','path':'/doorLocked','value':False}]
            elif is_relaxed:patch=[{'op':'replace','path':'/characters/Tom/mood','value':'relaxed'}]
            elif is_time:patch=[{'op':'set' if semantic else 'replace','path':'/time','value':'14:20'}]
            else:patch=[{'op':'list_add' if semantic else 'add','path':'/characters/Tom/clothing'+('' if semantic else '/-'),'value':'green jacket'}]
            text=canonical(patch)
        return {'text':text,'finish_reason':'stop','request_seconds':.02,'first_token_seconds':.01,
                'usage':{},'timings':{},'cached_tokens':1024 if cache=='on' and self.counter>1 else 0,
                'simulated':True,'raw_chunks':[]}
    @contextlib.contextmanager
    def budget(self,seconds,terminate_process=True):yield
