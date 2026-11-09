'use strict';
// Development-only differential driver. Runtime has no JavaScript dependency.
const fs=require('node:fs');const {spawnSync}=require('node:child_process');const {isDeepStrictEqual:equal}=require('node:util');
const baseline=process.env.JS_REFERENCE||'../csc592-intent-parser';const api=require(require('node:path').resolve(baseline,'index.cjs'));
const dotnet=process.env.DOTNET||'dotnet';const executable='bin/Debug/net8.0/IntentParser.dll';
const base={items:[{id:'a',score:1},{id:'b',score:2}],archive:[],a:0,b:0};
let cases=[];const add=(text,input=base,options={})=>cases.push({action:'normalize',text,input,options});
for(const word of ['add','append','insert','update','remove','delete','copy','move','ADD','Remove','set','merge','"remove"','"update"','null',''])
 for(const prefix of ['','op:','"operation"=>','type ->'])
  for(const path of ['path:items.a','["items","a"]','path:[]','path:"/items/a"','path:items . a','path:(items,a)','path:/items/a','path:items.a.','path:items//a'])
   add(prefix+word+' '+path+(word.toLowerCase().includes('update')?' value:3':''));
for(const newline of ['\n','\r\n','\r','\u2028','\u2029'])for(const before of ['',' ','\t',' \t '])for(const after of ['',' ','\t',' \t ']) {
 add('remove path:["a"]'+before+newline+after+'remove path:["b"]',{a:1,b:2});
 add('op:'+before+newline+after+'update'+before+newline+'path:["a"]'+before+newline+after+'value:2',{a:1});
}
for(const value of ['[]','{}','null','true','false','0','1.0','1e0','-0','1e-5','0.0000001','-1.5','1e-400','0e-400','1e309','9007199254740993','-9007199254740993','1e100','"hi"','{"a":[],"b":{},"c":[1,2]}','{"a":1,"a":2}','{"nested":{"a":1,"a":2}}','"a\\tb"','"a\\nb"','"\\ud800"','"😀"','"a\u2028b"']) {
 add('op:update path:a value:'+value,{a:0});
 add('op:remove path:["a",'+value+']',{a:[0,1,1.5,true,false,null,'1','hi']});
}
for(const key of ['/x','/','~1','~0','a.b','a/b','',':','remove','constructor','__proto__','a b','a\tb','a\nb'])add('op:update path:'+JSON.stringify([key])+' value:1',{[key]:0});
for(const text of ['('.repeat(65)+'remove path:a'+')'.repeat(65),'remove\na\nb\nc\nremove','[]','()','{}','[\n]','null','(remove path:a','remove path:a)','(append path:a value:[1,2','[{remove path:a},{remove path:b}]','remove path:a; remove path:b','remove path:a\nremove path:b'])add(text,{a:1,b:2});
add('remove path:a',{}, {maxChars:2}); add('remove path:a\nremove path:b',base,{maxBoundaryAttempts:0});add('(remove path:a)(remove path:b)',{a:1,b:2},{maxOperations:1});
for(const whitespace of ['\u000b','\u000c','\u00a0','\u1680','\u2000','\u202f','\u205f','\u3000','\ufeff','\u0085'])add('remove'+whitespace+'path:a',{a:0});
for(const op of ['remove','update']) for(const suffix of ['a','_',':','-','9','é','İ','K'])add('op:'+op+suffix+' path:a value:2',{a:0});
for(const text of ['path: /items/a remove','path: (items.a) remove','copy (items.a) to:archive','append (archive) {"id":"c"}','{"id":"c"} append (archive)','update (items.a.score) "copy"','update 3 path:items.a.score','append ["a"] ["b"]','update path:items.a.id value:"new"; update path:items.new.score value:2'])add(text);
const lines=cases.map(x=>JSON.stringify(x)).join('\n')+'\n';
const run=spawnSync(dotnet,[executable,'--json-lines'],{input:lines,encoding:'utf8',maxBuffer:30*1024*1024});if(run.status)throw Error(run.stderr);
const results=run.stdout.trim().split('\n').map(JSON.parse);let failed=[];let accepted=0;
for(let i=0;i<cases.length;i++) {
 const c=cases[i]; let reference;
 try{reference={ok:true,result:api.normalizeIntent(c.text,c.input,c.options)};accepted++;}catch(error){reference={ok:false,error:error.message};}
 if(reference.ok!==results[i]?.ok||reference.ok&&!equal(reference.result,results[i].result))failed.push({case:c,reference,actual:results[i]});
}
fs.writeFileSync('differential-results.json',JSON.stringify({total:cases.length,accepted,failed:failed.length,failures:failed},null,2)+'\n');
console.log(JSON.stringify({total:cases.length,accepted,failed:failed.length}));if(failed.length){console.log(JSON.stringify(failed.slice(0,10),null,2));process.exitCode=1;}
