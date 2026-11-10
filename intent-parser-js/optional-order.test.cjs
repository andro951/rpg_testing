const assert=require('node:assert/strict');
const {parseIntent,parseIntentWithDiagnostics}=require('./parse.cjs');
const {convertIntent,applyPatch}=require('./patch.cjs');
const fs=require('node:fs');
function perms(a){return a.length?a.flatMap((x,i)=>perms(a.filter((_,j)=>j!==i)).map(t=>[x,...t])):[[]];}
const input={items:[{id:'a',score:1},{id:'b',score:2}],archive:[]};
const cases=[
 {parts:[['op','update'],['path','["items","a","score"]'],['value','3']],expected:{items:[{id:'a',score:3},{id:'b',score:2}],archive:[]}},
 {parts:[['op','append'],['path','["archive"]'],['value','{"id":"c"}']],expected:{items:input.items,archive:[{id:'c'}]}},
 {parts:[['op','remove'],['path','["items","a"]']],expected:{items:[input.items[1]],archive:[]}},
 {parts:[['op','copy'],['from','["items","a"]'],['to','["archive"]']],expected:{items:input.items,archive:[input.items[0]]}},
 {parts:[['op','move'],['from','["items","a"]'],['to','["archive"]']],expected:{items:[input.items[1]],archive:[input.items[0]]}},
];
let passed=0;const fixtures=[];
for(const c of cases)for(const parts of perms(c.parts))for(let mask=0;mask<(1<<parts.length);mask++)for(const separator of [' ','\n']){
 const text=parts.map(([label,value],i)=>(mask&(1<<i)?label+':':'')+value).join(separator);
 const custom=convertIntent(parseIntent(text),input);
 assert.deepEqual(applyPatch(input,custom),c.expected,text);passed++;
 fixtures.push({name:'optional labels/order',text,input,expected:c.expected});
}
const sequences=[
 'op:remove\npath:["items","a"]\nop:update\npath:["items","b","score"]\nvalue:5',
 '["items","a"]\nremove\nvalue:5\n["items","b","score"]\nupdate',
 '(op:remove path:items.a;op:update path:items.b.score value:5)',
 'remove path:items.a\nupdate path:items.b.score value:5',
];
for(const text of sequences){const expected={items:[{id:'b',score:5}],archive:[]};assert.deepEqual(applyPatch(input,convertIntent(parseIntent(text),input)),expected,text);fixtures.push({name:'unique newline sequence',text,input,expected});passed++;}
for(const text of ['op:update path:["items","a","score"] value:"x\\ny"','{"op":"update","path":["items","a","score"],"value":"x\\ny"}']){
 assert.equal(applyPatch(input,convertIntent(parseIntent(text),input)).items[0].score,'x\ny');passed++;
}
assert.throws(()=>parseIntent('('.repeat(65)+'remove path:a'+')'.repeat(65)),/depth/);passed++;
assert.throws(()=>parseIntent('remove path:a',{maxChars:2}),/size/);passed++;
assert.throws(()=>parseIntent('remove path:a\nremove path:b',{maxBoundaryAttempts:0}),/complexity/);passed++;
assert.throws(()=>parseIntent('(remove path:a)(remove path:b)',{maxOperations:1}),/count/);passed++;
fs.writeFileSync(__dirname+'/optional-parity-fixtures.json',JSON.stringify(fixtures)+'\n');
console.log(JSON.stringify({passed,failed:0,parityFixtures:fixtures.length}));
