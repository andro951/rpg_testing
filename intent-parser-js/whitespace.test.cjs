const assert=require('node:assert/strict');
const {parseIntent}=require('./parse.cjs');const {convertIntent,applyPatch}=require('./patch.cjs');
let passed=0;
for(const newline of ['\n','\r\n','\r','\u2028','\u2029'])for(const before of ['',' ','\t',' \t '])for(const after of ['',' ','\t',' \t ']){
 const text='remove path:["a"]'+before+newline+after+'remove path:["b"]';
 assert.deepEqual(applyPatch({a:1,b:2},convertIntent(parseIntent(text),{a:1,b:2})),{},JSON.stringify(text));passed++;
 const multiline='op:'+before+newline+after+'update'+before+newline+'path:["a"]'+before+newline+after+'value:2';
 assert.deepEqual(applyPatch({a:1},convertIntent(parseIntent(multiline),{a:1})),{a:2});passed++;
}
for(const value of ['a b','a\tb','a\nb','a\r\nb','op: remove; path:["x"]','a\u2028b','"quoted" \\ end']){
 const text='op:update path:["a"] value:'+JSON.stringify(value);
 assert.equal(applyPatch({a:''},convertIntent(parseIntent(text),{a:''})).a,value);passed++;
}
for(const key of ['a b','a\tb','a\nb','a.b/c','op:remove','']){
 const input={[key]:0};const text='op:update path:'+JSON.stringify([key])+' value:1';
 assert.equal(applyPatch(input,convertIntent(parseIntent(text),input))[key],1);passed++;
}
for(const control of ['\n','\r','\t']){assert.throws(()=>parseIntent('op:update path:a value:"x'+control+'y"'));passed++;}
assert.throws(()=>parseIntent('remove\na\nb\nc\nremove'),/Ambiguous|No complete operation sequence/);passed++;
console.log(JSON.stringify({passed,failed:0,scope:'actual bundled GrammarForge whitespace priority, line boundaries and quoted values'}));
