'use strict';
// Export GrammarForge's own parsed rule objects. This is deliberately not a
// second grammar parser: all syntax and rule validation starts in GrammarForge.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const GF=require('./load-forge.cjs');
const simplify=(op,xs)=>xs.length===1?xs[0]:[op,xs];
function expList(list){return simplify('|',list.expressions.map(expression=>{
 if(expression.metadata.length)throw Error('Grammar metadata is not supported by the portable exporter');
 return simplify(',',expression.words.map(word));
}));}
function word(w){
 if(w.oType){
  const op={QUESTION:'?',STAR:'*',PLUS:'+'}[w.oType];
  if(!op||w.delimiterWord)throw Error('Unsupported grammar repetition '+w.oType);
  return [op,word(w.word)];
 }
 if(w.expList)return expList(w.expList);
 if(!['TOKEN','IDENTIFIER'].includes(w.type))throw Error('Unsupported grammar term '+w.type);
 return w.value;
}
function validateSpec(spec){
 const {rules,tokens}=spec,terminals=new Set(tokens.map(t=>t.type)),nullable=new Set();
 function canEmpty(e){
  if(typeof e==='string')return nullable.has(e);
  const [op,body]=e;
  if(op==='?'||op==='*')return true;
  if(op==='+')return canEmpty(body);
  return op==='|'?body.some(canEmpty):body.every(canEmpty);
 }
 let changed=true;while(changed){changed=false;for(const [name,expr] of Object.entries(rules))if(!nullable.has(name)&&canEmpty(expr)){nullable.add(name);changed=true;}}
 const refs=e=>typeof e==='string'?[e]:e[0]==='|'||e[0]===','?e[1].flatMap(refs):refs(e[1]);
 function check(e){
  if(typeof e==='string'){if(!Object.hasOwn(rules,e)&&!terminals.has(e))throw Error('Unknown grammar reference '+e);return;}
  const [op,body]=e;
  if((op==='*'||op==='+')&&canEmpty(body))throw Error('Nullable repetition could loop forever');
  if(op==='|'||op===',')body.forEach(check);else check(body);
 }
 const leading=e=>{
  if(typeof e==='string')return Object.hasOwn(rules,e)?[e]:[];
  const [op,body]=e;if(op==='|')return body.flatMap(leading);
  if(op!==',')return leading(body);
  const found=[];for(const part of body){found.push(...leading(part));if(!canEmpty(part))break;}return found;
 };
 const edges={};for(const [name,expr] of Object.entries(rules)){check(expr);edges[name]=leading(expr);}
 const done=new Set(),active=new Set();function visit(name){if(active.has(name))throw Error('Nullable-prefix left recursion: '+name);if(done.has(name))return;active.add(name);edges[name].forEach(visit);active.delete(name);done.add(name);}Object.keys(rules).forEach(visit);
 if(!Object.hasOwn(rules,spec.start))throw Error('Unknown start rule');
 return spec;
}
function exportGrammar(text){
 const forge=new GF(text),rules=Object.fromEntries(forge.rules.map(r=>{if(r.tag)throw Error('Rule tags are not supported by portable exporter');return [r.name,expList(r.expList)];}));
 const tokens=forge.tokenDefinitions.map(t=>({type:t.type,source:t.regex.source,flags:t.regex.flags,tag:t.tag??null}));
 return validateSpec({start:forge.rules[0].name,rules,tokens});
}
function build(){
 const spec={version:1,sourceHashes:{},grammars:{}};
 const intent=fs.readFileSync(path.join(__dirname,'intent.grammar'),'utf8');
 const operation=intent.slice(intent.indexOf('operation :'));
 for(const name of ['intent','operation','tokens']){
  const text=name==='operation'?operation:fs.readFileSync(path.join(__dirname,name+'.grammar'),'utf8');
  spec.sourceHashes[name]=crypto.createHash('sha256').update(text).digest('hex');
  spec.grammars[name]=exportGrammar(text);
 }
 return spec;
}
function main(){
 const intent=fs.readFileSync(path.join(__dirname,'intent.grammar'),'utf8');
 const operation=intent.slice(intent.indexOf('operation :'));
 const operationPath=path.join(__dirname,'operation.grammar');
 if(process.argv.includes('--check')){if(fs.readFileSync(operationPath,'utf8')!==operation)throw Error('Stale operation.grammar projection');}else fs.writeFileSync(operationPath,operation);
 const text=JSON.stringify(build(),null,2)+'\n';
 for(const dir of ['intent-parser-js','intent_parser','intent-parser-csharp']){
  const target=path.join(__dirname,'..',dir,'grammar-spec.json');
  if(process.argv.includes('--check')){if(!fs.existsSync(target)||fs.readFileSync(target,'utf8')!==text)throw Error('Stale generated grammar: '+target);}
  else fs.writeFileSync(target,text);
  for(const name of ['intent','operation','tokens'])if(dir!=='intent-parser-js'){
   const source=fs.readFileSync(path.join(__dirname,name+'.grammar'),'utf8'),copy=path.join(__dirname,'..',dir,name+'.grammar');
   if(process.argv.includes('--check')){if(!fs.existsSync(copy)||fs.readFileSync(copy,'utf8')!==source)throw Error('Stale grammar source: '+copy);}else fs.writeFileSync(copy,source);
  }
 }
}
if(require.main===module)main();
module.exports={build,exportGrammar,validateSpec};
