const assert=require('node:assert/strict');const api=require('./index.cjs');let passed=0;
const input={values:[{id:'a',count:1}],other:[]};const text='update path:["values","a","count"] value:2';
const prompt=api.buildPrompt({request:'Set count to two.',document:input});
for(const op of ['Update:','Append:','Remove:','Copy:','Move:']){assert.ok(prompt.includes(op));passed++;}
assert.ok(!prompt.includes('Examples of syntax'));passed++;
const custom=api.normalizeIntent(text,input);assert.deepEqual(custom,[{op:'update',path:['values','a','count'],value:2}]);passed++;
const standard=api.normalizeIntent(text,input,{json_patch:true});assert.deepEqual(standard,[{op:'replace',path:'/values/0/count',value:2}]);passed++;
assert.deepEqual(api.applyPatch(input,custom),{values:[{id:'a',count:2}],other:[]});passed++;
assert.equal(input.values[0].count,1);passed++;
assert.deepEqual(api.normalizeIntent('',input),[]);passed++;
assert.throws(()=>api.buildPrompt({request:'x',document:undefined}));passed++;
assert.throws(()=>api.buildPrompt({request:'x',document:{x:Infinity}}));passed++;
assert.throws(()=>api.normalizeIntent('update path:missing value:2',input));passed++;
assert.deepEqual(api.normalizeIntent('remove path:["a","x"]',{a:[{key:'x'}]},{idKey:'key'}),[{op:'remove',path:['a','x']}]);passed++;
for(const empty of ['[]','()','{}','[\n]']){assert.deepEqual(api.normalizeIntent(empty,input),[]);passed++;}
assert.deepEqual(api.applyPatch([],api.normalizeIntent('[] append 3',[])),[3]);passed++;
assert.throws(()=>api.normalizeIntent('null',input));passed++;
console.log(JSON.stringify({passed,failed:0,scope:'public API including explicit empty operation list and root-array unlabeled append'}));
