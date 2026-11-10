'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const GF=require('./load-forge.cjs'),{exportGrammar,validateSpec}=require('./build-grammar-spec.cjs');
const api=require('./index.cjs');
const grammar=fs.readFileSync(path.join(__dirname,'intent.grammar'),'utf8');
const forge=new GF(grammar);let passed=0;
for(const text of ['remove path:a','path:a remove','(remove path:a)',
 '(((remove path:a)))','[{(remove path:a)}]',
 'op:update path:a value:{"op":"remove","path":"b","nested":[{"value":"copy"}]}',
 'update path:[\n"a"\n] value:{\n"x": [1,\n{"op":"remove"}]\n}',
 'to:["archive"] COPY source:["items","a"]',
 '{"op"\n:"update","path"\n:"a","value"\n:1}',
 '[] append 3','```JSON\nremove path:a\n```']){
 forge.parse(text);api.parseIntent(text);passed+=2;
}
// These are invalid at the grammar level, before conversion or document lookup.
for(const text of ['remove path:a value:1','update path:a','op:unknown path:a',
 'copy from:a','copy from:a to:b value:1','remove path:a path:b',
 'op:remove op:copy path:a','remove path:a remove path:b','(remove path:a]',
 'remove path:a trailing prose','update path:a value:{"x":}',
 'update path:a value:[1 2]','update path:a value:{op:1}']){assert.throws(()=>forge.parse(text),text);passed++;}
const previous=GF.makeFullAST;GF.makeFullAST=true;
let ast;try{ast=forge.parse('copy from:["items","a"] to:["archive"]');}finally{GF.makeFullAST=previous;}
const names=[];function visit(n){if(Array.isArray(n)){if(n[0]==='RULE')names.push(n[2]);n.forEach(visit);}else if(n?.nodes)visit(n.nodes);}visit(ast);
for(const name of ['prog','op_list','operation','move_copy','source_component','destination_component','arr_path']){assert(names.includes(name),name);passed++;}
assert.equal(api.parseIntent('('.repeat(64)+'remove path:a'+')'.repeat(64)).length,1);passed++;
assert.equal(api.parseIntent(Array(256).fill('remove path:a').join(';')).length,256);passed++;
assert.throws(()=>api.parseIntent(Array(1000).fill('remove path:a').join(';')),/Operation count limit/);passed++;
assert.throws(()=>api.normalizeIntent('copy (left) (right)',{left:[],right:[]}));passed++;
assert.throws(()=>api.normalizeIntent('append ["a"] ["b"]',{a:[],b:[]}));passed++;
const data={x:0};assert.deepEqual(api.applyPatch(data,api.normalizeIntent('update path:x value:{"op":"remove","path":"x"}',data)),{x:{op:'remove',path:'x'}});passed++;
// Additional build-time guard covers nullable-loop cases upstream misses.
assert.throws(()=>exportGrammar('s : (A?)*\nA : /a/ (KEEP)'),/Nullable repetition/);passed++;
assert.throws(()=>validateSpec({start:'s',rules:{s:['?', 'A'],unused:['|',[[',',['s','unused']],'A']]},tokens:[{type:'A'}]}),/left recursion/);passed++;
assert.throws(()=>validateSpec({start:'s',rules:{s:'missing'},tokens:[]}),/Unknown grammar reference/);passed++;
const check=spawnSync(process.execPath,[path.join(__dirname,'build-grammar-spec.cjs'),'--check'],{encoding:'utf8'});assert.equal(check.status,0,check.stderr);passed++;
console.log(JSON.stringify({passed,failed:0,scope:'grammar-enforced operations, recursive values/groups, portability freshness and nullable-loop guards'}));
