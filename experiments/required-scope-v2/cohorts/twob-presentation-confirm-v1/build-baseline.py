from pathlib import Path
b=Path(__file__).resolve().parent;src=b.parent/'dot-rewrite-heldout-baseline-v1'/'build.py'
s=src.read_text(encoding='utf8').replace("out=base/'dot-rewrite-heldout-baseline-v1'", "out=base/'twob-presentation-confirm-v1'/'baseline'")
start=s.index('s1=obj(');end=s.index('for c in items:',start)
cases=r'''
s1=obj({'depot':obj({'sections':arr(obj({'section_id':S,'boxes':arr(obj({'box_id':S,'count':I}),'box_id')}),'section_id'),'name':S})})
state={'depot':{'sections':[{'section_id':'east','boxes':[{'box_id':'b1','count':1}]}],'name':'A'}};item={'box_id':'b2','count':3};y=copy.deepcopy(state);y['depot']['sections'][0]['boxes'][0]['count']=2;y['depot']['sections'][0]['boxes'].append(item)
add('present_nested',s1,state,'In section east, set count of box b1 to 2, then append box '+json.dumps(item)+'. Preserve everything else.',[op('replace',('depot','sections','east','boxes','b1','count'),2),op('add',('depot','sections','east','boxes'),item)],y)
s2=obj({'station':obj({'announcements':arr(obj({'announcement_id':S,'text':S}),'announcement_id'),'name':S})})
state={'station':{'announcements':[{'announcement_id':'a1','text':'old'},{'announcement_id':'a2','text':'keep'}],'name':'Central'}};value='She said "wait"\nnext train';y=copy.deepcopy(state);y['station']['announcements'][0]['text']=value
add('present_text',s2,state,'Set text of announcement a1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('station','announcements','a1','text'),value)],y)
s3=obj({'orchard':obj({'trees':arr(obj({'tree_id':S,'name':S}),'tree_id'),'owner':S})})
state={'orchard':{'trees':[{'tree_id':'t1','name':'keep'},{'tree_id':'t2','name':'remove'},{'tree_id':'t3','name':'keep'}],'owner':'Kai'}};y=copy.deepcopy(state);y['orchard']['trees'].pop(1)
add('present_remove',s3,state,'Remove tree t2 from orchard trees. Preserve everything else.',[op('remove',('orchard','trees','t2'))],y)
s4=obj({'cabinet':obj({'files':arr(obj({'file_id':S,'note':S}),'file_id'),'label':S})})
state={'cabinet':{'files':[{'file_id':'f1','note':'old'}],'label':'Home'}};value='  path \\n saved  ';y=copy.deepcopy(state);y['cabinet']['files'][0]['note']=value
add('present_literal',s4,state,'Set note of file f1 to the exact JSON string '+json.dumps(value)+'. Preserve everything else.',[op('replace',('cabinet','files','f1','note'),value)],y)
'''
s=s[:start]+cases+s[end:]
s=s.replace("for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:", "for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2')]:")
s=s.replace('assert len(requests)==54','assert len(requests)==12').replace("'dot-rewrite-heldout-baseline-v1'","'twob-presentation-confirm-baseline'")
s=s.replace('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.','Four new schemas and 12 baseline requests; references pass.')
exec(compile(s,str(src),'exec'))
