"""Build fresh 4B text-confirmation cases using the preserved dot baseline."""
from pathlib import Path
b=Path(__file__).resolve().parent
src=b.parent/'dot-rewrite-heldout-baseline-v1'/'build.py'
text=src.read_text(encoding='utf8').replace("out=base/'dot-rewrite-heldout-baseline-v1'", "out=base/'fourb-text-confirm-v1'/'baseline'")
start=text.index('s1=obj(');end=text.index('for c in items:',start)
cases=r'''
s1=obj({'bulletin':obj({'posts':arr(obj({'post_id':S,'body':S}),'post_id'),'site':S})})
state={'bulletin':{'posts':[{'post_id':'post1','body':'old'},{'post_id':'post2','body':'keep'}],'site':'N'}};value='She wrote "yes".';y=copy.deepcopy(state);y['bulletin']['posts'][0]['body']=value
add('quoted_text',s1,state,'Set body of post post1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('bulletin','posts','post1','body'),value)],y)
s2=obj({'observatory':obj({'entries':arr(obj({'entry_id':S,'note':S}),'entry_id'),'name':S})})
state={'observatory':{'entries':[{'entry_id':'entry1','note':'old'}],'name':'Hill'}};value='first line\nsecond line';y=copy.deepcopy(state);y['observatory']['entries'][0]['note']=value
add('line_break',s2,state,'Set note of entry entry1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('observatory','entries','entry1','note'),value)],y)
s3=obj({'catalog':obj({'files':arr(obj({'file_id':S,'path':S}),'file_id'),'label':S})})
state={'catalog':{'files':[{'file_id':'file1','path':'old'},{'file_id':'file2','path':'keep'}],'label':'C'}};value='literal \\n and \\"';y=copy.deepcopy(state);y['catalog']['files'][0]['path']=value
add('literal_slashes',s3,state,'Set path of file file1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('catalog','files','file1','path'),value)],y)
s4=obj({'meeting':obj({'items':arr(obj({'item_id':S,'summary':S}),'item_id'),'room':S})})
state={'meeting':{'items':[{'item_id':'i1','summary':'old'}],'room':'Blue'}};value='';y=copy.deepcopy(state);y['meeting']['items'][0]['summary']=value
add('empty_text',s4,state,'Set summary of item i1 to the empty string. Preserve everything else.',[op('replace',('meeting','items','i1','summary'),value)],y)
s5=obj({'hotel':obj({'rooms':arr(obj({'room_id':S,'notice':S}),'room_id'),'name':S})})
state={'hotel':{'rooms':[{'room_id':'r1','notice':'old'}],'name':'Lake'}};value='  welcome  ';y=copy.deepcopy(state);y['hotel']['rooms'][0]['notice']=value
add('edge_spaces',s5,state,'Set notice of room r1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('hotel','rooms','r1','notice'),value)],y)
s6=obj({'studio':obj({'boards':arr(obj({'board_id':S,'cards':arr(obj({'card_id':S,'label':S}),'card_id')}),'board_id'),'name':S})})
state={'studio':{'boards':[{'board_id':'b1','cards':[{'card_id':'c1','label':'old'},{'card_id':'c2','label':'remove'}]}],'name':'Art'}};item={'card_id':'c3','label':'雪 | "new"'};y=copy.deepcopy(state);y['studio']['boards'][0]['cards'][0]['label']='stage: ready';y['studio']['boards'][0]['cards'].pop(1);y['studio']['boards'][0]['cards'].append(item)
add('mixed_cards',s6,state,'On board b1, set card c1 label to "stage: ready", remove card c2, then append this complete card: '+json.dumps(item)+'. Preserve everything else.',[op('replace',('studio','boards','b1','cards','c1','label'),'stage: ready'),op('remove',('studio','boards','b1','cards','c2')),op('add',('studio','boards','b1','cards'),item)],y)
'''
text=text[:start]+cases+text[end:]
text=text.replace("for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:", "for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2')]:")
text=text.replace('assert len(requests)==54','assert len(requests)==18')
text=text.replace("'dot-rewrite-heldout-baseline-v1'","'fourb-text-confirm-baseline-v1'")
text=text.replace('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.','Six distinct schemas and 18 baseline requests; independent references pass.')
exec(compile(text,str(src),'exec'))
