'use strict';
const fs=require('node:fs');
const path=require('node:path');
const GF=require('./load-forge.cjs');
const safety=require('./json-contract.cjs');
const grammar=fs.readFileSync(path.join(__dirname,'intent.grammar'),'utf8');
const forge=new GF(grammar);
const operationForge=new GF(fs.readFileSync(path.join(__dirname,'operation.grammar'),'utf8'));
const operations=Object.assign(Object.create(null),{add:'append',append:'append',insert:'append',update:'update',remove:'remove',delete:'remove',copy:'copy',move:'move'});
const labels=Object.assign(Object.create(null),{op:'op',operation:'op',type:'op',path:'path',from:'from',source:'from',to:'to',destination:'to',value:'value'});
const opens={'(' : ')','[':']','{':'}'};
function simplify(x){
 if(Array.isArray(x)){
  if(x[0]?.value in opens) return {kind:'group',open:x[0].value,children:simplify(x[1])};
  return x.map(simplify);
 }
 return {kind:'token',type:x.type,text:x.value};
}
function flatten(x){return Array.isArray(x)?x.flatMap(flatten):[x];}
function lexParse(text){const tree=flatten(simplify(forge.parse(text)));function check(x){if(x.kind==='group')flatten(x.children).forEach(check);else if(x.type==='STRING')safety.unicode(JSON.parse(x.text));else if(x.type==='WORD')safety.unicode(x.text);else if(x.type==='NUMBER')safety.number(x.text);}tree.forEach(check);return tree;}
function isSep(x){return x.kind==='token'&&['SEP_COMMA','NEWLINE'].includes(x.type);}
function tokenValue(x){return x.type==='STRING'?JSON.parse(x.text):x.text;}
function render(x){if(x.kind==='group')return x.open+x.children.map(render).join(' ')+opens[x.open];return x.text;}
function pathTokens(xs){
 const explicitlyGrouped=xs.length===1&&xs[0].kind==='group';
 if(xs.length===1&&xs[0].kind==='group'){xs=flatten(xs[0].children);if(xs.length===0)return [];}
 if(xs.length===1&&xs[0].type==='STRING'){
  const s=tokenValue(xs[0]);
  // Quoted slash strings use RFC6901 escaping. Quoted literal segments use array notation.
  if(!explicitlyGrouped&&s.startsWith('/')){if(/~(?:[^01]|$)/.test(s))throw Error('Invalid JSON Pointer escape');return s.slice(1).split('/').map(p=>p.replace(/~1/g,'/').replace(/~0/g,'~'));}
  return [s];
 }
 const out=[];
 for(const x of xs){
  if(x.kind!=='token')throw Error('Nested path grouping is ambiguous');
  if(['PATH_SEPARATOR','SEP_COMMA','NEWLINE'].includes(x.type))continue;
  if(!['STRING','WORD','NUMBER'].includes(x.type))throw Error('Invalid path token');
  if(x.type==='NUMBER'&&Number.isInteger(Number(x.text))&&!Number.isSafeInteger(Number(x.text)))throw Error('Unsafe integer path token');
  out.push(x.type==='NUMBER'?JSON.parse(x.text):x.type==='WORD'&&['true','false','null'].includes(x.text)?JSON.parse(x.text):tokenValue(x));
 }
 if(!out.length)throw Error('Empty path requires explicit root representation');
 return out;
}
function valueOf(xs){
 if(xs.length===0)throw Error('Missing value');
 // JSON values remain strict. Intent grouping must never erase a broken value bracket.
 let value;try{value=JSON.parse(xs.map(render).join(' '));}catch{throw Error('Value must be intact JSON; cannot guess or repair its contents');}
 const checkGroup=x=>{if(x.kind!=='group')return;const children=flatten(x.children);if(x.open==='{'){
  const keys=new Set();for(let i=0;i<children.length-1;i++)if(children[i].type==='STRING'&&children[i+1].text===':'){
   const key=tokenValue(children[i]);if(keys.has(key))throw Error('Duplicate JSON value key');keys.add(key);
  }
 }children.forEach(checkGroup);};xs.forEach(checkGroup);
 const checkNumber=x=>{if(typeof x==='number'&&(!Number.isFinite(x)||(Number.isInteger(x)&&!Number.isSafeInteger(x))))throw Error('Nonfinite or unsafe JSON number');if(x&&typeof x==='object')Object.values(x).forEach(checkNumber);};checkNumber(value);
 return value;
}
function parseRecord(xs){
 xs=flatten(xs).filter(x=>!isSep(x));
 let ast;
 const previous=GF.makeFullAST;GF.makeFullAST=true;
 try{ast=operationForge.parse(xs.map(render).join(' '));}finally{GF.makeFullAST=previous;}
 const components=[];
 function collect(node){
  if(Array.isArray(node)){
   if(node[0]==='RULE'&&node[2]==='component'){components.push(node);return;}
   node.forEach(collect);
  }else if(node&&typeof node==='object'&&node.nodes)collect(node.nodes);
 }
 function leaves(node,out=[]){
  if(Array.isArray(node))node.forEach(x=>leaves(x,out));
  else if(node&&typeof node==='object'){if(node.type&&Object.hasOwn(node,'value'))out.push(node.value);else if(node.nodes)leaves(node.nodes,out);}
  return out;
 }
 collect(ast);
 const fields={};const unlabeled=[];
 for(const component of components){
  const items=lexParse(leaves(component).join(' '));
  const key=items[0]?.kind==='token'?labels[String(tokenValue(items[0])).toLowerCase()]:undefined;
  if(key&&items[1]?.type==='DELIMITER'){
   if(Object.hasOwn(fields,key))throw Error('Duplicate '+key+' label');
   fields[key]=items.slice(2);
  }else unlabeled.push(...items);
 }
 // A bare operation word following a labeled path can precede or follow the path.
 // Quoted path segments and separator-adjacent words are never reclassified.
 if(!fields.op&&!unlabeled.some(x=>x.type==='WORD'&&Object.hasOwn(operations,x.text.toLowerCase()))){
  const candidates=[];
  for(const k of ['path','from','to'])if(fields[k])fields[k].forEach((x,i)=>{
   if(x.type==='WORD'&&Object.hasOwn(operations,x.text.toLowerCase())&&fields[k][i-1]?.type!=='PATH_SEPARATOR'&&fields[k][i+1]?.type!=='PATH_SEPARATOR')candidates.push({k,i,x});
  });
  if(candidates.length===1){const {k,i,x}=candidates[0];fields[k].splice(i,1);unlabeled.push(x);}
 }
 let op;
 if(fields.op){if(fields.op.length!==1)throw Error('Exactly one operation type required');op=operations[String(tokenValue(fields.op[0])).toLowerCase()];}
 else{
  let positions=unlabeled.map((x,i)=>x.type==='WORD'&&operations[x.text.toLowerCase()]?i:-1).filter(i=>i>=0);
  if(!positions.length)positions=unlabeled.map((x,i)=>x.type==='STRING'&&operations[String(tokenValue(x)).toLowerCase()]?i:-1).filter(i=>i>=0);
  if(positions.length!==1)throw Error('Exactly one unambiguous operation type required');
  op=operations[String(tokenValue(unlabeled.splice(positions[0],1)[0])).toLowerCase()];
 }
 if(!op)throw Error('Unsupported or ambiguous operation alias');
 const ir={op};
 for(const k of ['path','from','to'])if(fields[k])ir[k]=pathTokens(fields[k]);
 if(fields.value)ir.value=valueOf(fields.value);
 if(['append','update'].includes(op)&&unlabeled.length){
  if(ir.path&&!Object.hasOwn(ir,'value')){ir.value=valueOf(unlabeled);unlabeled.length=0;}
  else if(!ir.path&&!Object.hasOwn(ir,'value')){
   const candidates=[];
   for(let split=1;split<unlabeled.length;split++)for(const [p,v] of [[unlabeled.slice(0,split),unlabeled.slice(split)],[unlabeled.slice(split),unlabeled.slice(0,split)]]){
    try{candidates.push({path:pathTokens(p),value:valueOf(v)});}catch{}
   }
   const unique=[...new Map(candidates.map(c=>[JSON.stringify(c),c])).values()];
   if(!unique.length)throw Error('Cannot distinguish unlabeled path and JSON value');
   ir.unlabeledPathValue=unique;unlabeled.length=0;
  }
 }
 if(unlabeled.length){
  if((op==='copy'||op==='move')&&!ir.path&&Boolean(ir.from)!==Boolean(ir.to)&&unlabeled.length===1&&(unlabeled[0].kind==='group'||unlabeled[0].type==='STRING')){
   ir[ir.from?'to':'from']=pathTokens(unlabeled);unlabeled.length=0;
  }
  if(unlabeled.length&&(ir.path||ir.from||ir.to))throw Error('Unlabeled component conflicts with labeled paths');
  if(unlabeled.length&&(op==='copy'||op==='move')){
   if(unlabeled.length!==2||!unlabeled.every(x=>x.kind==='group'||x.type==='STRING'))throw Error('Two unlabeled paths require explicit grouping');
   ir.unlabeledPaths=unlabeled.map(x=>pathTokens([x]));
  }else if(unlabeled.length)ir.path=pathTokens(unlabeled);
 }
 if(op==='copy'||op==='move'){
  if(Object.hasOwn(ir,'value'))throw Error('Copy/move use source path, not value');
  if(ir.path){if(ir.from&&!ir.to){ir.to=ir.path;delete ir.path;}else if(ir.to&&!ir.from){ir.from=ir.path;delete ir.path;}else throw Error('Copy/move path role ambiguous');}
  if(!ir.unlabeledPaths&&(!ir.from||!ir.to))throw Error('Copy/move needs source and destination');
 }else{
  if(ir.from||ir.to)throw Error('Directional paths not valid for this operation');
  if(!ir.path&&!ir.unlabeledPathValue)throw Error('Missing path');
  if(op==='remove'&&Object.hasOwn(ir,'value'))throw Error('Remove cannot carry a value');
  if(op!=='remove'&&!Object.hasOwn(ir,'value')&&!ir.unlabeledPathValue)throw Error('Missing value');
 }
 return ir;
}
function repairOuterWrapper(text,{maxDepth=64}={}){
 // Only one unmatched outer wrapper is recoverable. Never repair an inner JSON value.
 const stack=[];let quoted=false,escaped=false;const unmatched=[];
 for(let i=0;i<text.length;i++){
  const c=text[i];if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
  if(c==='"'){quoted=true;continue;}
  if(opens[c]){stack.push({c,i});if(stack.length>maxDepth)throw Error('Grouping depth limit exceeded');}
  else if(Object.values(opens).includes(c)){
   if(stack.length){if(opens[stack[stack.length-1].c]!==c)throw Error('Mismatched grouping');stack.pop();}
   else unmatched.push({c,i});
  }
 }
 if(quoted)throw Error('Unterminated quoted value');
 if(stack.length===1&&!unmatched.length&&stack[0].i===text.search(/\S/))return {text:text+opens[stack[0].c],repair:'missing outer closer'};
 if(!stack.length&&unmatched.length===1&&unmatched[0].i===text.trimEnd().length-1){
  const opener=Object.keys(opens).find(k=>opens[k]===unmatched[0].c);return {text:opener+text,repair:'missing outer opener'};
 }
 if(stack.length||unmatched.length)throw Error('Unbalanced inner grouping cannot be safely recovered');
 return {text,repair:null};
}
function hasOperation(node){const children=flatten(node.children);return children.some((x,i)=>x.kind==='group'?hasOperation(x):
 (['WORD','STRING'].includes(x.type)&&Object.hasOwn(operations,String(tokenValue(x)).toLowerCase()))||
 (labels[String(tokenValue(x)).toLowerCase()]==='op'&&children[i+1]?.type==='DELIMITER'));}
function parseIntent(text,options){return parseIntentWithDiagnostics(text,options).operations;}
function parseSequence(nodes,{maxBoundaryAttempts=4096,maxOperations=256}={}){
 nodes=flatten(nodes);while(nodes.length&&isSep(nodes[0]))nodes.shift();while(nodes.length&&isSep(nodes.at(-1)))nodes.pop();
 const compact=[];for(let i=0;i<nodes.length;i++){if(!isSep(nodes[i])){compact.push(nodes[i]);continue;}let chosen=nodes[i];while(i+1<nodes.length&&isSep(nodes[i+1])){i++;if(nodes[i].type==='NEWLINE')chosen=nodes[i];}compact.push(chosen);}nodes=compact;

 // Newlines are candidate boundaries, never unconditional boundaries.
 // Exhaust all complete grammatical partitions and accept exactly one meaning.
 const xs=flatten(nodes);
 if(xs.some(x=>x.type==='SEMICOLON')){
  const result=[];let segment=[];
  for(const x of [...xs,{type:'SEMICOLON'}]){if(x.type==='SEMICOLON'){if(segment.some(n=>!isSep(n)))result.push(...parseSequence(segment,{maxBoundaryAttempts,maxOperations}));segment=[];}else segment.push(x);}
  if(result.length>maxOperations)throw Error('Operation count limit exceeded');return result;
 }
 const boundaries=[0];
 xs.forEach((x,i)=>{if(x.type==='NEWLINE')boundaries.push(i+1);});
 if(boundaries.at(-1)!==xs.length)boundaries.push(xs.length);
 let attempts=0;const memo=new Map();
 function solve(start){
  if(start===xs.length)return [[]];
  if(memo.has(start))return memo.get(start);
  const results=new Map();
  for(const end of boundaries){
   if(end<=start)continue;
   const part=xs.slice(start,end);
   if(!part.some(x=>!isSep(x))){for(const tail of solve(end))results.set(JSON.stringify(tail),tail);continue;}
   if(++attempts>maxBoundaryAttempts)throw Error('Operation boundary complexity limit exceeded; use explicit groups or semicolons');
   let operation;try{operation=parseRecord(part);}catch{continue;}
   for(const tail of solve(end)){
    if(tail.length>=maxOperations)throw Error('Operation count limit exceeded');
    const candidate=[operation,...tail];results.set(JSON.stringify(candidate),candidate);
    if(results.size>1)break;
   }
   if(results.size>1)break;
  }
  const value=[...results.values()];memo.set(start,value);return value;
 }
 const candidates=solve(0);
 if(candidates.length!==1)throw Error(candidates.length?'Ambiguous newline operation boundaries':'No complete operation sequence');
 return candidates[0];
}
function unwrapFence(text){const m=/^\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*\s*$/i.exec(text);return m?{text:m[1],diagnostics:[{code:'MARKDOWN_FENCE_REMOVED',detail:'single enclosing JSON code fence'}]}:{text,diagnostics:[]};}
function parseIntentWithDiagnostics(text,options={}){
 if(typeof text!=='string')throw Error('Intent text must be a string');
 if(text.length>(options.maxChars??65536))throw Error('Intent text size limit exceeded');
 const unwrapped=unwrapFence(text),repaired=repairOuterWrapper(unwrapped.text,options),tree=lexParse(repaired.text);
 const diagnostics=[...unwrapped.diagnostics,...(repaired.repair?[{code:'OUTER_GROUP_RECOVERED',detail:repaired.repair}]:[])];
 const meaningful=tree.filter(x=>!isSep(x));
 if(meaningful.length===1&&meaningful[0].kind==='group'&&flatten(meaningful[0].children).every(isSep))return {operations:[],diagnostics};
 const candidates=new Map();const accept=r=>{if(r.length>(options.maxOperations??256))throw Error('Operation count limit exceeded');candidates.set(JSON.stringify(r),r);};
 const retain=e=>{if(/limit exceeded|Ambiguous/.test(e.message))throw e;};
 try{accept(parseSequence(tree,options));}catch(e){retain(e);}
 try{const records=[];let current=[];const flush=()=>{if(current.some(x=>!isSep(x)))records.push(...parseSequence(current,options));current=[];};
 for(const node of tree){
 if(node.kind==='token'&&node.type==='SEMICOLON'){flush();continue;}
 if(node.kind==='group'&&current.every(isSep)&&hasOperation(node)){flush();const inner=flatten(node.children).filter(x=>!isSep(x));if(inner.length&&inner.every(x=>x.kind==='group'))for(const child of inner)records.push(parseRecord(child.children));else records.push(...parseSequence(node.children,options));}else current.push(node);
 }flush();accept(records);}catch(e){retain(e);}
 if(candidates.size!==1)throw Error(candidates.size?'Ambiguous complete operation interpretations':'No complete operation sequence');
 return {operations:[...candidates.values()][0],diagnostics};
}
module.exports={parseIntent,parseIntentWithDiagnostics,parseRecord,parseSequence,lexParse,pathTokens,grammar};
