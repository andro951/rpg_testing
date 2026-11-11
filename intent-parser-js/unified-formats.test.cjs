'use strict';
const assert=require('node:assert/strict');
const {parseIntent,parseIntentWithDiagnostics}=require('./parse.cjs');
const {normalizeIntent,convertIntent,applyPatch}=require('./index.cjs');
let passed=0;
function test(name,fn){try{fn();passed++;}catch(e){e.message=name+': '+e.message;throw e;}}
const one=(s,options)=>parseIntent(s,options)[0];
for(const fixture of require('./unified-format-fixtures.json'))test('parity: '+fixture.name,()=>{
 if(fixture.reject)assert.throws(()=>parseIntent(fixture.text,fixture.options));
 else assert.deepEqual(parseIntent(fixture.text,fixture.options),fixture.expected);
});

test('all explicit output forms',()=>{
 for(const s of ['update: /x\nvalue: 2','update /x: 2','set: /x\nnumber: 2','update /x: number: +2'])
  assert.deepEqual(one(s),{op:'update',path:['x'],value:2});
 assert.deepEqual(one('append: /xs\njson: {"id":"a"}'),{op:'append',path:['xs'],value:{id:'a'}});
 assert.deepEqual(one('copy: /xs/"a"\nto: /ys'),{op:'copy',from:['xs','a'],to:['ys']});
 assert.deepEqual(one('move /xs/"a" -> /ys'),{op:'move',from:['xs','a'],to:['ys']});
 assert.deepEqual(parseIntent('none'),[]);
});
test('typed scalars and empty containers',()=>{
 for(const [source,value] of [['text:',''],['number: -1.5',-1.5],['boolean: false',false],['null:',null],['object:',{}],['list:',[]],['json: [1,true,null]',[1,true,null]]])
  assert.deepEqual(one('set /x: '+source).value,value);
});
test('raw text boundaries preserve exact source',()=>{
 const raw='  hello  "unmatched [ { } : value: ->  ';
 assert.equal(one('set: /x\ntext:'+raw).value,raw);
 assert.equal(one('set: /x\ntext:'+raw,{output_format:'typed_lines'}).value,raw.slice(1));
 assert.equal(one('set: /x\ntext:'+raw+'\nremove: /y').value,raw);
 assert.equal(one('set: /x\ntext: [([([(',{maxDepth:1}).value,' [([([(');
});
test('text codecs',()=>{
 assert.equal(one('set /x: text:\\sA\\nB\\t\\r\\\\\\"',{output_format:'literal_line'}).value,' A\nB\t\r\\"');
 assert.equal(one('set /x: text: a|b\\n|',{output_format:'end_marked_line'}).value,' a|b\n');
 for(const [source,format] of [['text: a','end_marked_line'],['text: \\q','literal_line'],['text: \\s|','end_marked_line']])
  assert.throws(()=>one('set /x: '+source,{output_format:format}));
});
test('typed slash paths preserve identities and field names',()=>{
 assert.deepEqual(one('set: /first name/a.b/"2"/2/true/null/"a/b"\nnumber: 1').path,['first name','a.b','2',2,true,null,'a/b']);
});
test('semantic markers fail closed in standalone normalization',()=>{
 assert.deepEqual(one('change: /x\nnumber: +2'),{op:'update',path:['x'],value:2,semantic:'numeric_delta'});
 assert.equal(one('remove path:/x',{output_format:'typed_lines'}).semantic,'typed_remove');
 assert.throws(()=>normalizeIntent('change: /x\nnumber: +2',{x:1}));
 assert.throws(()=>normalizeIntent('remove: /x',{x:1},{output_format:'typed_lines'}));
});
test('strict typed values and safety',()=>{
 for(const source of ['number: + 2','number: 9007199254740992','number: 1e-999','boolean: 1','null: 1','object: []','list: {}','json: "text"','json: {"a":1,"a":2}','json: {"n":9007199254740992}','text:\ud800'])
  assert.throws(()=>one('set /x: '+source),source);
 assert.throws(()=>one('change: /x\nvalue: 2'));
 assert.throws(()=>one('change: /x\ntext: 2'));
});
test('wrappers and fences retain conservative recovery',()=>{
 assert.deepEqual(parseIntentWithDiagnostics('(remove path:/x').diagnostics,[{code:'OUTER_GROUP_RECOVERED',detail:'missing outer closer'}]);
 assert.equal(one('```json\nset: /x\ntext: " [\n```').value,' " [');
 assert.throws(()=>one('set /x: json: {"x": [1}'));
});
test('literal add resolves from target state',()=>{
 for(const text of ['add path:x value:2','add (x) 2','add /x: number: 2']){
  assert.deepEqual(normalizeIntent(text,{x:1}),[{op:'update',path:['x'],value:2}]);
  assert.deepEqual(normalizeIntent(text,{x:[]}),[{op:'append',path:['x'],value:2}]);
  assert.deepEqual(normalizeIntent(text,{x:1},{json_patch:true}),[{op:'replace',path:'/x',value:2}]);
 }
 assert.deepEqual(normalizeIntent('add path:x value:2',{x:{a:1}}),[{op:'update',path:['x'],value:2}]);
 assert.deepEqual(normalizeIntent('add path:[] value:2',[]),[{op:'append',path:[],value:2}]);
 for(const verb of ['append','insert'])assert.throws(()=>normalizeIntent(verb+' path:x value:2',{x:1}));
 assert.throws(()=>normalizeIntent('add path:[] value:2',1));
 assert.throws(()=>normalizeIntent('add path:xs.a value:2',{xs:[{id:'a'}]}));
 assert.throws(()=>normalizeIntent('add path:xs.1 value:2',{xs:[1]}));
 assert.throws(()=>normalizeIntent('add path:missing value:2',{}));
 assert.throws(()=>applyPatch({x:1},parseIntent('add path:x value:2')));
 assert.throws(()=>convertIntent([{op:'update',path:['x'],value:2,semantic:'literal_add'}],{x:1}));
 assert.throws(()=>convertIntent([{op:'append',path:['x'],value:2,semantic:'unknown'}],{x:[]}));
});
console.log(JSON.stringify({passed,failed:0,scope:'shared grammar structured output forms and exact text codecs'}));
