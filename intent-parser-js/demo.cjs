const {parseIntentWithDiagnostics}=require('./parse.cjs');
const {convertIntent,applyPatch}=require('./patch.cjs');
const {buildPrompt}=require('./prompt.cjs');
const input={items:[{id:'a',name:'Map',count:1},{id:'b',name:'Key',count:1}],archive:[]};
const program=`
(path: ["items","a","count"] value: 2 op: update)
(to: ["archive"] op: move from: ["items","b"])
`;
const parsed=parseIntentWithDiagnostics(program);
const custom=convertIntent(parsed.operations,input);
console.log(JSON.stringify({program,parsed,custom,result:applyPatch(input,custom),standard:convertIntent(parsed.operations,input,{json_patch:true}),prompt:buildPrompt({request:'Set the map count to two and move the key to archive.',document:input})},null,2));
