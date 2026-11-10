const assert=require('node:assert/strict');const {parseIntent}=require('./parse.cjs');const {convertIntent,applyPatch}=require('./patch.cjs');let passed=0;
for(const key of ['/x','/','~1','~0','a.b','a/b','',':','remove']){
 const input={[key]:0};const ir=parseIntent('op:update path:'+JSON.stringify([key])+' value:1');
 assert.deepEqual(ir[0].path,[key]);assert.equal(applyPatch(input,convertIntent(ir,input))[key],1);passed++;
}
const input={'a/b':{'~':0}};assert.deepEqual(applyPatch(input,convertIntent(parseIntent('op:update path:"/a~1b/~0" value:1'),input)),{'a/b':{'~':1}});passed++;
assert.throws(()=>parseIntent('op:remove path:"/a~2b"'));passed++;
for(const n of ['9007199254740993','-9007199254740993','1e100']){assert.throws(()=>parseIntent('op:update path:a value:'+n));assert.throws(()=>parseIntent('op:remove path:["a",'+n+']'));passed+=2;}
assert.throws(()=>convertIntent(parseIntent('op:update path:["a",1] value:2'),{a:[1,2]}));passed++;
const changed=convertIntent(parseIntent('update path:["a","old","id"] value:"new"; update path:["a","new","v"] value:2'),{a:[{id:'old',v:0}]});
assert.deepEqual(applyPatch({a:[{id:'old',v:0}]},changed),{a:[{id:'new',v:2}]});passed++;
assert.deepEqual(applyPatch({id:'x'},convertIntent(parseIntent('update path:id value:"y"'),{id:'x'})),{id:'y'});passed++;
assert.throws(()=>convertIntent(parseIntent('update path:["a","old","id"] value:{}'),{a:[{id:'old'}]}));passed++;
console.log(JSON.stringify({passed,failed:0,scope:'identity and precision including unique scalar identity updates'}));
