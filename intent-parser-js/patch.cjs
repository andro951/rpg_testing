'use strict';
function assertJSON(x,seen=new Set()){
 if(x===null||typeof x==='string'||typeof x==='boolean')return;
 if(typeof x==='number'){if(!Number.isFinite(x))throw Error('Nonfinite JSON number');return;}
 if(typeof x!=='object')throw Error('Non-JSON value');
 if(seen.has(x))throw Error('Cyclic JSON value');
 if(!Array.isArray(x)&&Object.getPrototypeOf(x)!==Object.prototype&&Object.getPrototypeOf(x)!==null)throw Error('Non-JSON object');
 seen.add(x);if(Array.isArray(x)){for(let i=0;i<x.length;i++){if(!Object.hasOwn(x,i))throw Error('Sparse JSON array');assertJSON(x[i],seen);}}else Object.values(x).forEach(v=>assertJSON(v,seen));seen.delete(x);
}
const clone=x=>{assertJSON(x);return JSON.parse(JSON.stringify(x));};
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
function resolve(root,path,{idKey='id'}={}){
 let node=root;const pointer=[];let parent=null,key=null;
 for(const segment of path){
  parent=node;
  if(Array.isArray(node)){
   const matches=[];for(let i=0;i<node.length;i++)if(node[i]&&typeof node[i]==='object'?own(node[i],idKey)&&JSON.stringify(node[i][idKey])===JSON.stringify(segment):JSON.stringify(node[i])===JSON.stringify(segment))matches.push(i);
   if(matches.length!==1)throw Error('Array ID must resolve exactly once: '+segment);
   key=matches[0];
  }else if(node!==null&&typeof node==='object'&&own(node,segment))key=segment;
  else throw Error('Missing path segment: '+segment);
  pointer.push(String(key));node=node[key];
 }
 return {node,parent,key,pointer};
}
const ptr=parts=>parts.length?'/'+parts.map(s=>s.replace(/~/g,'~0').replace(/\//g,'~1')).join('/'):'';
function setOwn(obj,key,value){Object.defineProperty(obj,key,{value,writable:true,enumerable:true,configurable:true});}
function deleteResolved(r){if(r.parent===null)throw Error('Root removal unsupported');if(Array.isArray(r.parent))r.parent.splice(r.key,1);else delete r.parent[r.key];}
function checkIdAppend(array,value,idKey){
 if((value===null||typeof value!=='object')&&array.some(v=>JSON.stringify(v)===JSON.stringify(value)))throw Error('Append would duplicate primitive identity');
 if(value&&typeof value==='object'&&own(value,idKey)&&array.some(v=>v&&typeof v==='object'&&own(v,idKey)&&JSON.stringify(v[idKey])===JSON.stringify(value[idKey])))throw Error('Append would create ambiguous duplicate identity');
}
function concrete(op,state,options){
 op=clone(op);
 if(op.unlabeledPathValue){
  const valid=[];
  for(const candidate of op.unlabeledPathValue){
   const trial={op:op.op,...candidate};
   try{execute(clone(state),trial,options);valid.push(trial);}catch{}
  }
  if(valid.length!==1)throw Error('Unlabeled path/value must resolve uniquely');
  return valid[0];
 }
 if(op.unlabeledPaths){
  const a=resolve(state,op.unlabeledPaths[0],options),b=resolve(state,op.unlabeledPaths[1],options);
  if(Array.isArray(a.node)===Array.isArray(b.node))throw Error('Unlabeled source/destination ambiguous');
  [op.from,op.to]=Array.isArray(a.node)?[op.unlabeledPaths[1],op.unlabeledPaths[0]]:op.unlabeledPaths;
  delete op.unlabeledPaths;
 }
 return op;
}
function execute(state,op,options){
 const idKey=options.idKey||'id';
 if(['copy','move'].includes(op.op)){
  const source=resolve(state,op.from,options),dest=resolve(state,op.to,options);
  if(!Array.isArray(dest.node))throw Error('Destination must be a collection');
  if(source.parent===dest.node)throw Error('Same-collection transfer unsupported');
  if(op.from.length<=op.to.length&&op.from.every((x,i)=>x===op.to[i]))throw Error('Transfer into source or descendant unsupported');
  // Appending inside source then deleting source would discard destination.
  if(op.op==='move'&&op.from.length<=op.to.length&&op.from.every((x,i)=>x===op.to[i]))throw Error('Cannot move source into itself or descendant');
  checkIdAppend(dest.node,source.node,idKey);
  const value=clone(source.node);
  const patch=[{op:'add',path:ptr(dest.pointer)+'/-',value:clone(value)}];
  dest.node.push(value);
  if(op.op==='move'){patch.push({op:'remove',path:ptr(source.pointer)});deleteResolved(source);}
  return patch;
 }
 const r=resolve(state,op.path,options);
 if(op.op==='append'){
  if(!Array.isArray(r.node))throw Error('Append target must be collection');
  checkIdAppend(r.node,op.value,idKey);r.node.push(clone(op.value));
  return [{op:'add',path:ptr(r.pointer)+'/-',value:clone(op.value)}];
 }
 if(op.op==='update'){
  if(!r.parent)throw Error('Root replacement unsupported');
  // Identity changes can invalidate later ID-addressed operations; do not silently introduce duplicates.
  if(r.key===idKey)throw Error('Identity-field update requires explicit policy');
  if(Array.isArray(r.parent)&&op.value&&typeof op.value==='object'&&own(op.value,idKey)){
   if(r.parent.some((v,i)=>i!==r.key&&v&&typeof v==='object'&&own(v,idKey)&&JSON.stringify(v[idKey])===JSON.stringify(op.value[idKey])))throw Error('Update would create ambiguous duplicate identity');
  }
  setOwn(r.parent,r.key,clone(op.value));return [{op:'replace',path:ptr(r.pointer),value:clone(op.value)}];
 }
 if(op.op==='remove'){deleteResolved(r);return [{op:'remove',path:ptr(r.pointer)}];}
 throw Error('Unsupported operation');
}
function validateShape(op){
 if(!op||typeof op!=='object'||!['append','update','remove','copy','move'].includes(op.op))throw Error('Invalid operation');
 const two=['copy','move'].includes(op.op), allowed=two?['op','from','to','unlabeledPaths']:['op','path',...(op.op==='remove'?[]:['value','unlabeledPathValue'])];
 if(Object.keys(op).some(k=>!allowed.includes(k)))throw Error('Unexpected operation field');
 for(const k of ['path','from','to'])if(own(op,k)&&(!Array.isArray(op[k])||!op[k].every(x=>x===null||['string','number','boolean'].includes(typeof x))))throw Error('Path must contain scalar JSON tokens');
 if(two){if(op.unlabeledPaths&&(!Array.isArray(op.unlabeledPaths)||op.unlabeledPaths.length!==2||!op.unlabeledPaths.every(p=>Array.isArray(p)&&p.every(x=>x===null||['string','number','boolean'].includes(typeof x)))))throw Error('Invalid unlabeled paths');if(!op.unlabeledPaths&&(!op.from||!op.to))throw Error('Missing directional path');}
 else if(!op.unlabeledPathValue&&(!op.path||(op.op!=='remove'&&!own(op,'value'))))throw Error('Missing path/value');
}
function convertIntent(ir,input,{json_patch=false,idKey='id'}={}){
 if(!Array.isArray(ir))throw Error('Operation list required');
 const state=clone(input),custom=[],standard=[];
 for(const raw of ir){validateShape(raw);const op=concrete(raw,state,{idKey});standard.push(...execute(state,op,{idKey}));custom.push(op);}
 return json_patch?standard:custom;
}
function applyPatch(input,patch,options={}){
 const state=clone(input);
 for(const op of patch){validateShape(op);if(op.unlabeledPaths||op.unlabeledPathValue)throw Error('Custom patch must have resolved roles');execute(state,op,options);}
 return state;
}
module.exports={convertIntent,applyPatch,resolve};
