"""Build fresh, predeclared VL8 confirmation cases using the unmodified baseline recipe."""
from pathlib import Path

base = Path(__file__).resolve().parent
workspace = base.parent
src = workspace / 'dot-rewrite-heldout-baseline-v1' / 'build.py'
text = src.read_text(encoding='utf8')
text = text.replace("out=base/'dot-rewrite-heldout-baseline-v1'", "out=base/'vl8-copy-confirm-v1'/'baseline'")
start = text.index("s1=obj(")
end = text.index("for c in items:", start)
cases = '''
# Six fresh schemas: four ordinary IDs, two reserved IDs. Expected states are
# independently constructed; reference patches are checked below.
s1=obj({'library':obj({'shelves':arr(obj({'shelf_id':S,'books':arr(obj({'book_id':S,'title':S}),'book_id')}),'shelf_id'),'open':B})})
state={'library':{'shelves':[{'shelf_id':'north','books':[{'book_id':'bk1','title':'old'}]}],'open':True}}; y=copy.deepcopy(state); y['library']['shelves'][0]['books'][0]['title']='Winter'; book={'book_id':'bk2','title':'Summer'}; y['library']['shelves'][0]['books'].append(book)
add('library_mixed',s1,state,'On shelf north, rename book bk1 to Winter and then append book '+json.dumps(book)+'. Preserve everything else.',[op('replace',('library','shelves','north','books','bk1','title'),'Winter'),op('add',('library','shelves','north','books'),book)],y)
s2=obj({'workshop':obj({'tools':arr(obj({'tool_id':S,'label':S,'active':B}),'tool_id'),'owner':S})})
state={'workshop':{'tools':[{'tool_id':'tool-a','label':'Saw','active':True},{'tool_id':'tool-b','label':'Drill','active':True}],'owner':'Rae'}};y=copy.deepcopy(state);y['workshop']['tools'].pop(1)
add('tool_remove',s2,state,'Remove the tool whose tool_id is tool-b. Preserve everything else.',[op('remove',('workshop','tools','tool-b'))],y)
s3=obj({'fleet':obj({'vehicles':arr(obj({'vehicle_id':S,'fuel':I,'route':S}),'vehicle_id'),'depot':S})})
state={'fleet':{'vehicles':[{'vehicle_id':'van-a','fuel':4,'route':'east'},{'vehicle_id':'van-b','fuel':9,'route':'west'}],'depot':'C'}};y=copy.deepcopy(state);y['fleet']['vehicles'][1]['fuel']=15
add('fuel_update',s3,state,'Set fuel of vehicle van-b to 15. Preserve everything else.',[op('replace',('fleet','vehicles','van-b','fuel'),15)],y)
s4=obj({'garden':obj({'plots':arr(obj({'plot_id':S,'crop':S}),'plot_id'),'name':S})})
state={'garden':{'plots':[{'plot_id':'p1','crop':'peas'}],'name':'Hill'}};item={'plot_id':'p2','crop':'beans'};y=copy.deepcopy(state);y['garden']['plots'].append(item)
add('plot_append',s4,state,'Append this plot to garden plots: '+json.dumps(item)+'. Preserve everything else.',[op('add',('garden','plots'),item)],y)
s5=obj({'warehouse':obj({'crates':arr(obj({'crate_id':S,'count':I}),'crate_id'),'city':S})})
state={'warehouse':{'crates':[{'crate_id':'box#7','count':3},{'crate_id':'box8','count':5}],'city':'A'}};y=copy.deepcopy(state);y['warehouse']['crates'].pop(0)
add('crate_remove_reserved',s5,state,'Remove crate with crate_id "box#7". Preserve everything else.',[op('remove',('warehouse','crates','box#7'))],y)
s6=obj({'clinic':obj({'wards':arr(obj({'ward_id':S,'beds':arr(obj({'bed_id':S,'occupied':B}),'bed_id')}),'ward_id'),'name':S})})
state={'clinic':{'wards':[{'ward_id':'w/2','beds':[{'bed_id':'b1','occupied':False}]}],'name':'Elm'}};y=copy.deepcopy(state);y['clinic']['wards'][0]['beds'][0]['occupied']=True
add('bed_update_reserved',s6,state,'In ward "w/2", set occupied for bed b1 to true. Preserve everything else.',[op('replace',('clinic','wards','w/2','beds','b1','occupied'),True)],y)
'''
text = text[:start] + cases + text[end:]
text = text.replace("for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:", "for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2')]:")
text = text.replace('assert len(requests)==54', 'assert len(requests)==18')
text = text.replace("'dot-rewrite-heldout-baseline-v1'", "'vl8-copy-confirm-baseline-v1'")
text = text.replace('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.', 'Six new fixtures across six schemas, 18 baseline requests; original prompt instructions unchanged; independent expected states and both evaluators pass.')
exec(compile(text, str(src), 'exec'))
