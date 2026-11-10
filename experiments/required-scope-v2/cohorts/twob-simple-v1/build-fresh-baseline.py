from pathlib import Path
b=Path(__file__).resolve().parent;src=b.parent/'dot-rewrite-heldout-baseline-v1'/'build.py'
s=src.read_text(encoding='utf8').replace("out=base/'dot-rewrite-heldout-baseline-v1'", "out=base/'twob-simple-v1'/'fresh-baseline'")
start=s.index('s1=obj(');end=s.index('for c in items:',start)
cases=r'''
s1=obj({'campus':obj({'classes':arr(obj({'class_id':S,'students':arr(obj({'student_id':S,'mark':I}),'student_id')}),'class_id'),'name':S})})
state={'campus':{'classes':[{'class_id':'c1','students':[{'student_id':'s1','mark':1}]}],'name':'North'}};new={'student_id':'s2','mark':3};y=copy.deepcopy(state);y['campus']['classes'][0]['students'][0]['mark']=2;y['campus']['classes'][0]['students'].append(new)
add('twob_nested',s1,state,'In class c1, set student s1 mark to 2, then append student '+json.dumps(new)+'. Preserve everything else.',[op('replace',('campus','classes','c1','students','s1','mark'),2),op('add',('campus','classes','c1','students'),new)],y)
s2=obj({'desk':obj({'notes':arr(obj({'note_id':S,'body':S}),'note_id'),'team':S})})
state={'desk':{'notes':[{'note_id':'n1','body':'old'},{'note_id':'n2','body':'remove'},{'note_id':'n3','body':'keep'}],'team':'A'}};value='  "hello"\nnext  ';y=copy.deepcopy(state);y['desk']['notes'][0]['body']=value;y['desk']['notes'].pop(1)
add('twob_text_remove',s2,state,'Set body of note n1 to the exact JSON string '+json.dumps(value)+', then remove note n2. Preserve everything else.',[op('replace',('desk','notes','n1','body'),value),op('remove',('desk','notes','n2'))],y)
'''
s=s[:start]+cases+s[end:]
s=s.replace("for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:", "for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2')]:")
s=s.replace('assert len(requests)==54','assert len(requests)==6').replace("'dot-rewrite-heldout-baseline-v1'","'twob-fresh-baseline'")
s=s.replace('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.','Two new schemas and six baseline requests; references pass.')
exec(compile(s,str(src),'exec'))
