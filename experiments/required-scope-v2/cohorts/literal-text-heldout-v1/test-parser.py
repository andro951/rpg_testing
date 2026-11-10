import copy,sys
from pathlib import Path
root=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\literal-text-branch-v1\runtime');sys.path.insert(0,str(root));from workbench.literal_line import encode,decode,apply
S={'type':'string'};I={'type':'integer'}
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
schema=obj({'groups':{'type':'array','x-id-field':'group_id','items':obj({'group_id':S,'items':{'type':'array','x-id-field':'item_id','items':obj({'item_id':S,'text':S,'rank':I})}})},'other':S})
state={'groups':[{'group_id':'g1','items':[{'item_id':'x1','text':'old','rank':1},{'item_id':'x2','text':'keep','rank':2}]}],'other':'preserve'}
texts=['','  leading','trailing  ','  both  ','quote " inside','literal \\n','real\nnewline','backslash \\ then n','carriage\rreturn','colon: text: json: =','tab\tinside','snow-雪','line\u2028separator']
for value in texts:
 ops=[{'op':'replace','path':'groups.g1.items.x1.text','value':value}];wire=encode(ops);assert decode(wire)==ops,(repr(value),repr(wire));expected=copy.deepcopy(state);expected['groups'][0]['items'][0]['text']=value;assert apply(state,wire,schema)==expected
ops=[{'op':'replace','path':'groups.g1.items.x1.rank','value':7},{'op':'remove','path':'groups.g1.items.x2'},{'op':'add','path':'groups.g1.items','value':{'item_id':'x3','text':'quoted " and newline\n','rank':3}}];wire=encode(ops);assert decode(wire)==ops;expected=copy.deepcopy(state);expected['groups'][0]['items'][0]['rank']=7;expected['groups'][0]['items'].pop(1);expected['groups'][0]['items'].append({'item_id':'x3','text':'quoted " and newline\n','rank':3});assert apply(state,wire,schema)==expected
for raw in ['set groups.g1.items.x1.text: text:bad\\q','set groups.g1.items.x1.text: json:"quoted"','set groups.g1.items.x1.text: text:bad\\','remove groups.g1.items.x2: text:x','set groups.g1.items.x1.text: text:a\nb']:
 try:decode(raw)
 except ValueError:continue
 raise AssertionError(('accepted invalid',raw))
assert decode('none')==[];print('PASS: 13 literal text round-trips including empty/whitespace/quotes/backslash-n/newlines/CR/delimiters/Unicode; nested typed mixed operations preserve unrelated state; five malformed cases rejected.')
