from pathlib import Path
b=Path(__file__).resolve().parent;src=b.parent/'dot-rewrite-heldout-baseline-v1'/'build.py'
text=src.read_text(encoding='utf8').replace("out=base/'dot-rewrite-heldout-baseline-v1'", "out=base/'nineb-copy-confirm-v1'/'baseline'")
start=text.index('s1=obj(');end=text.index('for c in items:',start)
cases=r'''
s1=obj({'correspondence':obj({'messages':arr(obj({'message_id':S,'body':S}),'message_id'),'name':S})})
state={'correspondence':{'messages':[{'message_id':'m1','body':'old'},{'message_id':'m2','body':'keep'}],'name':'North'}};value='She said "go"\nthen waited';y=copy.deepcopy(state);y['correspondence']['messages'][0]['body']=value
add('fresh_message',s1,state,'Set body of message m1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('correspondence','messages','m1','body'),value)],y)
s2=obj({'university':obj({'courses':arr(obj({'course_id':S,'students':arr(obj({'student_id':S,'score':I}),'student_id')}),'course_id'),'term':S})})
state={'university':{'courses':[{'course_id':'c1','students':[{'student_id':'s1','score':2}]}],'term':'Fall'}};new={'student_id':'s2','score':7};y=copy.deepcopy(state);y['university']['courses'][0]['students'][0]['score']=6;y['university']['courses'][0]['students'].append(new)
add('fresh_nested_add',s2,state,'In course c1, set student s1 score to 6, then append this student: '+json.dumps(new)+'. Preserve everything else.',[op('replace',('university','courses','c1','students','s1','score'),6),op('add',('university','courses','c1','students'),new)],y)
s3=obj({'stockroom':obj({'items':arr(obj({'item_id':S,'label':S}),'item_id'),'location':S})})
state={'stockroom':{'items':[{'item_id':'i1','label':'keep'},{'item_id':'i2','label':'remove'},{'item_id':'i3','label':'keep2'}],'location':'Main'}};y=copy.deepcopy(state);y['stockroom']['items'].pop(1)
add('fresh_remove',s3,state,'Remove item i2 from the stockroom. Preserve everything else.',[op('remove',('stockroom','items','i2'))],y)
s4=obj({'service':obj({'tickets':arr(obj({'ticket_id':S,'note':S}),'ticket_id'),'team':S})})
state={'service':{'tickets':[{'ticket_id':'t1','note':'old'},{'ticket_id':'t2','note':'keep'}],'team':'A'}};value='  literal \\n remains  ';y=copy.deepcopy(state);y['service']['tickets'][0]['note']=value
add('fresh_literal_text',s4,state,'Set note of ticket t1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('service','tickets','t1','note'),value)],y)
'''
text=text[:start]+cases+text[end:]
text=text.replace("for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:", "for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2')]:")
text=text.replace('assert len(requests)==54','assert len(requests)==12').replace("'dot-rewrite-heldout-baseline-v1'","'nineb-copy-confirm-baseline-v1'")
text=text.replace('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.','Four new schemas and 12 baseline requests; independent references pass.')
exec(compile(text,str(src),'exec'))
