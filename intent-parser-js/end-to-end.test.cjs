'use strict';
const assert=require('node:assert/strict');const fs=require('node:fs');
const {parseIntent}=require('./parse.cjs');const {convertIntent,applyPatch}=require('./patch.cjs');const {buildPrompt}=require('./prompt.cjs');
const fixtures=require('./fixtures.cjs');
function permutations(a){return a.length?a.flatMap((x,i)=>permutations(a.filter((_,j)=>j!==i)).map(rest=>[x,...rest])):[[]];}
// Independent RFC subset interpreter. Does not use custom ID resolver/updater.
function applyRFC(input,patch){const state=JSON.parse(JSON.stringify(input));for(const op of patch){const parts=op.path.slice(1).split('/').map(x=>x.replace(/~1/g,'/').replace(/~0/g,'~'));const key=parts.pop();let parent=state;for(const part of parts)parent=parent[part];if(op.op==='remove'){if(Array.isArray(parent))parent.splice(Number(key),1);else delete parent[key];}else if(op.op==='add'&&Array.isArray(parent)){assert.equal(key,'-');parent.push(op.value);}else if(op.op==='replace'){assert.ok(Object.hasOwn(parent,key));Object.defineProperty(parent,key,{value:op.value,writable:true,enumerable:true,configurable:true});}else throw Error('Unsupported reference op');}return state;}
let passed=0;const shared=[],parity=[];
for(const f of fixtures){
 for(const keys of permutations(Object.keys(f.fields)))for(const delim of [':','=','=>','->'])for(const [left,right] of [['(',')'],['{','}'],['[',']']])for(const join of [' ', ', ', '\n']){
  const text=left+keys.map(k=>k+delim+f.fields[k]).join(join)+right;
  const before=JSON.stringify(f.input);
  const prompt=buildPrompt({request:f.name,document:f.input});assert.ok(prompt.includes(before));assert.ok(prompt.endsWith(f.name));
  const ir=parseIntent(text),custom=convertIntent(ir,f.input),standard=convertIntent(ir,f.input,{json_patch:true});
  assert.deepEqual(applyPatch(f.input,custom),f.expected,text);assert.deepEqual(applyRFC(f.input,standard),f.expected,text);
  assert.equal(JSON.stringify(f.input),before);passed++;
  parity.push({name:f.name,input:f.input,text,ir,custom,standard,expected:f.expected});
  if(keys.join()===Object.keys(f.fields).join()&&delim===':'&&left==='('&&join===' ')shared.push({name:f.name,input:f.input,text,ir,custom,standard,expected:f.expected});
 }
}
const reject=[
 ['duplicate field','op:remove path:items.a path:items.b'],
 ['unknown operation','op:merge path:items value:{}'],
 ['conflicting direction','op:move from:items.a source:items.b to:archive'],
 ['unlabeled collections','copy (items) (archive)'],
 ['missing value','op:update path:items.a.count'],
 ['duplicate IDs','op:copy from:items.a to:items'],
 ['positional insert','op:insert path:items before:a value:{}'],
 ['missing inner bracket','op:append path:items value:[1,2'],
 ['unexpected prose','Certainly op:remove path:items.a'],
 ['unknown field','op:remove path:items.a reason:ok'],
 ['numeric index','op:remove path:items.0'],
 ['wrong destination type','op:copy from:items.a to:items.b.count'],
 ['identity update','op:update path:items.a.id value:"b"'],
 ['duplicate ID replacement','op:update path:items.a value:{"id":"b"}'],
 ['multiple operations without boundary','op:remove path:items.a op:remove path:items.b'],
];
for(const [name,text] of reject){assert.throws(()=>convertIntent(parseIntent(text),fixtures[0].input),name);shared.push({name,text,input:fixtures[0].input,reject:true});parity.push({name,text,input:fixtures[0].input,reject:true});passed++;}
for(const bad of [NaN,Infinity,undefined,()=>1,BigInt(3),new Date()]){assert.throws(()=>convertIntent([{op:'update',path:['items','a','count'],value:bad}],fixtures[0].input));passed++;}
assert.equal({}.x,undefined);
fs.writeFileSync(__dirname+'/parity-fixtures.json',JSON.stringify(parity)+'\n');
fs.writeFileSync(__dirname+'/shared-fixtures.json',JSON.stringify(shared,null,2)+'\n');
console.log(JSON.stringify({passed,failed:0,sharedFixtures:shared.length,parityFixtures:parity.length,scope:'deterministic prompt construction + simulated response + actual GrammarForge + IR + custom/RFC conversion + two independent applicators; no live model calls'}));
