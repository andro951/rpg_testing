"""Synthetic candidates only. Does not alter active suite or run inference."""
import copy,json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1] if (OUT.parents[1]/'prompt_builder').is_dir() else Path('/workspace/scratch/d62d07f7dfca/592-review')
if not (ROOT/'prompt_builder').is_dir():
 ROOT=Path('/tmp/592-review')
if not (ROOT/'prompt_builder').is_dir():
 raise RuntimeError('Place this generator under the repository scripts/context_candidates directory.')
sys.path.insert(0,str(ROOT))
from evaluation.array_identities_intent import apply_patch,validate_data
from prompt_builder.builder import prompt,applicable,validate_presentation_identity
from prompt_builder.reference_output import encode
from workbench.self_review import REVIEW_QUESTION,REPLACEMENT_REQUEST
FORMATS=['json_dot','json_slash','path_list','literal_line','end_marked_line','typed_lines'];VIEWS=['normal_json','id_keyed_arrays','full_paths']
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def medical(n):
 clinics=[{'id':'clinic-north','name':'North Clinic','capacity':28},{'id':'clinic-central','name':'Central Clinic','capacity':46},{'id':'clinic-west','name':'West Clinic','capacity':32}]
 clinicians=[{'id':f'doc-{i+1:02}','name':['Avery Chen','Morgan Patel','Jordan Reed','Casey Torres'][i],'clinic_id':clinics[i%3]['id'],'specialty':['family medicine','cardiology','endocrinology','pulmonology'][i]} for i in range(4)]
 given=['Alex','Jamie','Taylor','Robin','Sam','Dana','Lee','Quinn'];family=['Bennett','Rivera','Park','Singh','Morgan','Owens','Chen','Reed']
 patients=[];visits=[]
 for i in range(n):
  patients.append({'id':f'patient-{i+1:03}','name':given[i%8]+' '+family[(i//8)%8],'age':19+(i*7)%69,'clinician_id':clinicians[i%4]['id'],'condition':['hypertension','asthma','type2_diabetes','migraine','none'][i%5],'medication':['lisinopril','albuterol','metformin','sumatriptan','none'][i%5],'follow_up':['routine','due','scheduled'][i%3],'consent':i%9!=0})
  if i%4==0:visits.append({'id':f'visit-{i+1:03}','patient_id':patients[-1]['id'],'clinic_id':clinics[i%3]['id'],'date':f'2026-12-{1+i%28:02}','kind':['review','lab','consult'][i%3],'status':['booked','arrived','complete'][i%3]})
 archived=copy.deepcopy(patients[:2])
 for i,p in enumerate(archived):p.update(id=f'patient-archived-{i+1:03}',follow_up='routine')
 new=copy.deepcopy(patients[-1]);new.update(id='patient-new-901',name='Elliot Brooks',age=42,follow_up='scheduled')
 state={'clinics':clinics,'clinicians':clinicians,'patients':patients,'transferred_patients':archived,'appointments':visits}
 return state,[(k,'id') for k in state], 'patients','transferred_patients',patients[n//2]['id'],new,'follow_up','scheduled' if patients[n//2]['follow_up']!='scheduled' else 'due','Synthetic outpatient registry with patients linked to clinicians and appointments linked to patients/clinics. Transfer removes only registry element; no appointment references selected patient.'
def shipping(n):
 warehouses=[{'id':'wh-east','city':'Baltimore','capacity_pallets':640},{'id':'wh-west','city':'Tacoma','capacity_pallets':520},{'id':'wh-south','city':'Savannah','capacity_pallets':720}]
 carriers=[{'id':'carrier-road','mode':'road','max_kg':18000},{'id':'carrier-rail','mode':'rail','max_kg':68000},{'id':'carrier-ocean','mode':'ocean','max_kg':24000}]
 products=[{'id':'sku-filter','description':'Water filter cartridge','unit_kg':0.65},{'id':'sku-motor','description':'Pump motor assembly','unit_kg':14.5},{'id':'sku-glove','description':'Work glove carton','unit_kg':3.2},{'id':'sku-panel','description':'Solar panel crate','unit_kg':28.0}]
 shipments=[]
 for i in range(n):
  shipments.append({'id':f'shipment-{i+1:03}','origin_id':warehouses[i%3]['id'],'carrier_id':carriers[i%3]['id'],'destination':['Denver','Albany','Portland','Austin','Columbus'][i%5],'product_id':products[i%4]['id'],'units':2+(i*11)%90,'weight_kg':round(products[i%4]['unit_kg']*(2+(i*11)%90),2),'status':['queued','packed','in_transit'][i%3],'priority':['standard','express'][i%2]})
 completed=copy.deepcopy(shipments[:2])
 for i,s in enumerate(completed):s.update(id=f'shipment-delivered-{i+1:03}',status='delivered')
 new=copy.deepcopy(shipments[-1]);new.update(id='shipment-new-901',destination='Phoenix',status='queued')
 # Both collections are dispatch queues. Transfer does not imply status mutation.
 state={'warehouses':warehouses,'carriers':carriers,'products':products,'dispatch_queue':shipments,'overflow_queue':completed,'capacity':{'reserved_pallets':38,'available_pallets':142}}
 state['overflow_queue'][0]['status']='queued';state['overflow_queue'][1]['status']='packed'
 return state,[(k,'id') for k in ['warehouses','carriers','products','dispatch_queue','overflow_queue']],'dispatch_queue','overflow_queue',shipments[n//2]['id'],new,'priority','express' if shipments[n//2]['priority']!='express' else 'standard','Synthetic shipping database with warehouse/carrier/product relationships, measured cargo weights and independent overflow dispatch queue.'
def generate(kind,n):
 state,decl,src,dst,target,new,field,value,description=globals()[kind](n)
 # Selected patient must have no appointment references when testing standalone Remove/Move.
 if kind=='medical':
  choices=[p for p in state[src] if all(v['patient_id']!=p['id'] for v in state['appointments'])];target=choices[len(choices)//2]['id'];value='scheduled' if next(p for p in state[src] if p['id']==target)['follow_up']!='scheduled' else 'due'
 ids=[{'path':[p],'id_field':f} for p,f in decl];validate_data(state,ids)
 name=f'{kind}-{n:03}';d=OUT/name;d.mkdir(exist_ok=True);write(d/'starting_data.json',state);write(d/'array_identities.json',ids)
 patches={'update':[{'op':'replace','path':f'{src}.{target}.{field}','value':value}],'append':[{'op':'add','path':src,'value':new}],'remove':[{'op':'remove','path':f'{src}.{target}'}],'move':[{'op':'move','from':f'{src}.{target}','path':dst}],'copy':[{'op':'copy','from':f'{src}.{target}','path':dst}],'no_op':[]}
 requests={'update':f'In {src}, set the {field} field of the element with ID {target} to {json.dumps(value)}.','append':f'Append this complete element to {src}: '+json.dumps(new),'remove':f'Remove the element with ID {target} from {src}.','move':f'Move the complete element with ID {target} from {src} to {dst}; leave all its fields unchanged.','copy':f'Copy the complete element with ID {target} from {src} to {dst}, preserving every field and leaving the source unchanged.','no_op':'The training handbook should use blue headings and a serif font.'}
 rows=[]
 for action,patch in patches.items():
  expected=apply_patch(state,patch,ids)['final_state'];validate_data(expected,ids)
  case={'id':name+'__'+action,'starting_data':state,'array_identities':ids,'expected_patch':patch,'expected_result':expected,'requested_change':requests[action]};write(d/(action+'.json'),case)
  validate_presentation_identity(case,VIEWS)
  for fmt in FORMATS:
   assert applicable(case,fmt) is None,(name,action,fmt,applicable(case,fmt))
   reference=encode(state,patch,fmt,ids)
   for view in VIEWS:
    msgs=prompt(case,view,fmt);pd=d/'rendered_prompts';pd.mkdir(exist_ok=True);write(pd/f'{action}__{view}__{fmt}.json',msgs);content=''.join(m['content'] for m in msgs)
    # Reference replay size, NOT a worst-case guarantee: actual wrong answers may be much larger.
    cumulative=copy.deepcopy(msgs)
    for attempt in range(4):
     cumulative.extend([{'role':'assistant','content':reference},{'role':'user','content':REVIEW_QUESTION}])
     if attempt<3:cumulative.extend([{'role':'assistant','content':'no'},{'role':'user','content':REPLACEMENT_REQUEST}])
    rows.append({'action':action,'view':view,'format':fmt,'initial_content_chars':len(content),'initial_content_utf8_bytes':len(content.encode()),'messages_json_utf8_bytes':len(json.dumps(msgs,ensure_ascii=False).encode()),'reference_answer_chars':len(reference),'four_answer_review_content_chars':sum(len(m['content']) for m in cumulative),'token_count':None})
 write(d/'measurements.json',rows)
 return {'candidate':name,'description':description,'primary_records':n,'total_record_elements':sum(len(v) for v in state.values() if isinstance(v,list)),'pretty_json_bytes':len(json.dumps(state,ensure_ascii=False,indent=2).encode()),'compact_json_bytes':len(json.dumps(state,ensure_ascii=False,separators=(',',':')).encode()),'max_initial_chars':max(r['initial_content_chars'] for r in rows),'max_reference_cumulative_chars':max(r['four_answer_review_content_chars'] for r in rows)}
if __name__=='__main__':
 summaries=[generate(k,n) for k,ns in [('medical',[20,40,80,120]),('shipping',[25,50,100,150])] for n in ns];write(OUT/'candidate_summary.json',summaries);print(json.dumps(summaries,indent=2))
