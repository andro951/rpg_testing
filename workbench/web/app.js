'use strict';
const $=id=>document.getElementById(id);
let key=sessionStorage.getItem('rpg-worker-key')||'';
const fragment=new URLSearchParams(location.hash.slice(1));
if(fragment.has('key')){key=fragment.get('key');sessionStorage.setItem('rpg-worker-key',key);history.replaceState(null,'',location.pathname);}
let state=null,page='overview',records=[],testData=[],polling=false,setupDirty=false;
$('page-setup').addEventListener('input',()=>{setupDirty=true;});
$('page-setup').addEventListener('change',()=>{setupDirty=true;});
const titles={overview:'Overview',models:'Models',tests:'Test definitions',results:'Results',find:'Find models',runtime:'Native runtime',analysis:'Comparison',logs:'Logs',setup:'Worker setup'};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function showAlert(message,title='Notice'){ $('alert-title').textContent=title;$('alert-text').textContent=message;if(!$('alert').open)$('alert').showModal(); }
function toast(text){$('toast').textContent=text;$('toast').classList.remove('hidden');setTimeout(()=>$('toast').classList.add('hidden'),3500);}
async function api(path,body){const options={headers:{Authorization:'Bearer '+key}};if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}const r=await fetch(path,options);if(r.status===403){if(!$('login').open)$('login').showModal();throw Error('Pair this browser with the worker.');}if(!r.ok){let msg='Request failed';try{msg=(await r.json()).error||msg;}catch{}throw Error(msg);}if(r.headers.get('Content-Type')?.includes('application/json'))return r.json();return r.blob();}
function on(id,fn){$(id).addEventListener('click',async()=>{try{await fn();}catch(e){showAlert(e.message);}});}
function button(text,fn,cls){const b=el('button',text,cls);b.addEventListener('click',async()=>{try{await fn();}catch(e){showAlert(e.message);}});return b;}
function setPage(name){page=name;document.querySelectorAll('.page').forEach(n=>n.classList.toggle('hidden',n.id!=='page-'+name));document.querySelectorAll('nav button').forEach(n=>n.classList.toggle('selected',n.dataset.page===name));$('page-title').textContent=titles[name];if(name==='tests')loadTests().catch(e=>showAlert(e.message));if(name==='results')loadResults().catch(e=>showAlert(e.message));if(name==='analysis')loadAnalysis().catch(e=>showAlert(e.message));}
document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
document.querySelectorAll('.close-dialog').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
function render(s){state=s;const p=s.report?.plan;const busy=s.busy;$('connection').textContent='● Connected to worker';$('state-badge').textContent=s.state.toUpperCase().replaceAll('_',' ');$('demo').classList.toggle('hidden',!s.demo);$('message').textContent=s.message;$('gpu').textContent=s.report?.gpu?.name||(s.demo?'SIMULATED GTX 1080':'Your GPU worker');$('pending').textContent=p?.pending??'—';$('complete').textContent=p?.complete??'—';$('session-complete').textContent=s.completed_now;$('loads').textContent=p?.model_loads??'—';
const prog=s.progress||{};const taskPct=Math.max(0,Math.min(100,Number(prog.task_percent)||0));const overallPct=Math.max(0,Math.min(100,Number(prog.overall_percent)||0));
$('current').textContent=prog.task|| (s.current?Object.entries(s.current).filter(([k,v])=>typeof v!=='object').map(([k,v])=>k+': '+v).join(' · '):s.message);$('progress-detail').textContent=prog.detail||'';$('task-progress').value=taskPct;$('task-percent').textContent=taskPct.toFixed(1)+'%';$('progress').value=overallPct;$('overall-percent').textContent=overallPct.toFixed(1)+'%';
const place=s.current?.placement;$('placement').textContent=place?('Placement: '+place.status+' · GPU layers '+place.gpu_layers+'/'+place.total_layers+' · CPU layers '+place.cpu_layers):'';
const mem=s.telemetry?.latest;$('gpu-memory').textContent=mem?('Whole-device VRAM: '+(mem.used_bytes/2**30).toFixed(2)+' / '+(mem.total_bytes/2**30).toFixed(2)+' GiB'+(s.current?'':' · Last sample')):('GPU memory: '+(s.telemetry?.error||'No sample yet'));
['preflight','run','rescan','prepare','save-setup','new-test','import-example','refresh-results','export','enable-remote','disable-remote','hub-search','hub-download','runtime-list','runtime-install','select-recommended','refresh-analysis'].forEach(id=>$(id).disabled=busy);
$('pause').disabled=s.state!=='running';$('resume').disabled=s.state!=='paused';$('stop-model').disabled=!['running','paused'].includes(s.state);$('stop').disabled=!busy;$('restart').classList.toggle('hidden',!s.restart_required);$('run').disabled=busy||s.restart_required;
$('readiness').textContent=!s.report?'Not checked':s.report.preparation_only?(s.report.prepared?'Prepared (GPU not verified)':'Preparation blocked'):(s.report.ready?'Ready':'Needs attention');
const issues=$('issues');issues.replaceChildren();if(s.report){if(!s.report.issues.length)issues.append(el('p',s.report.note,'muted'));for(const i of s.report.issues){const row=el('div',undefined,'issue '+i.level);row.append(el('span',i.level.toUpperCase(),'label'),el('p',i.message));if(i.action){const b=button(i.label,async()=>{if(i.action.type==='setup'||i.action.type==='choose_folder'){setPage('setup');return;}if(i.action.type==='models'){setPage('models');return;}if(i.action.type==='runtime'){setPage('runtime');return;}if(!confirm(i.label+'?\n\nOnly this action will be performed. Downloads may use substantial disk space.'))return;await api('/api/fix',{issue_id:i.id});await poll();});b.disabled=busy;row.append(b);}issues.append(row);}}
const plan=$('plan');plan.replaceChildren();for(const g of p?.groups||[]){const n=el('div',undefined,'plan-item');n.append(el('b',g.model_id),el('p',g.pending+' pending · '+g.complete+' complete · '+g.reason,'muted'));if(g.context)n.append(el('p','Automatic context allocation: '+g.context.allocated_tokens.toLocaleString()+' tokens','muted'));plan.append(n);}if(p&&!p.groups.length)plan.append(el('p','No models match this hardware tier.','muted'));
$('folder-note').textContent=s.report?.folder?.path?('Active folder: '+s.report.folder.path+' · '+s.report.folder.source):'No active model folder detected yet.';
renderModels();$('log-view').textContent=s.logs.map(l=>l.time+' ['+l.category+'] '+l.message).join('\n');$('remote-url').textContent=s.remote?.url||'';
if(!setupDirty&&!$('page-setup').contains(document.activeElement)){ $('model-root').value=s.settings.model_root;$('llama-path').value=s.settings.llama_path;$('sync-source').checked=s.settings.sync_source;$('publish-results').checked=s.settings.publish_results; }
renderHub();renderRuntimes();folderPrompts();
}
let modelRenderSignature='',modelVramDrafts=new Map();
async function saveModelVram(model,tier){
 await api('/api/model/assign',{id:model.id,required_vram_gb:tier});
 modelVramDrafts.delete(model.id);
 render(await api('/api/state'));
 toast(model.name+' assigned to '+tier+' GB. Run preflight when ready.');
}
function renderModels(){
 const list=$('model-list');
 const signature=JSON.stringify([state.models,state.busy,state.demo,[...modelVramDrafts.entries()]]);
 if(signature===modelRenderSignature)return;
 modelRenderSignature=signature;list.replaceChildren();
 for(const m of state.models){
  const assigned=m.required_vram_gb??null;
  const card=el('article',undefined,'model-card');
  const heading=el('div',undefined,'section-header');heading.append(el('h3',m.name),el('span',m.quantization,'badge'));
  card.append(heading,el('p',(m.size_bytes/1e9).toFixed(2)+' GB download · '+(m.complete?'All shards found':'Missing shards')+' · '+(assigned===null?'VRAM: Unassigned':'VRAM: '+assigned+' GB assigned')));
  const controls=el('div',undefined,'actions');
  const select=el('select');select.setAttribute('aria-label','VRAM for '+m.id);select.append(new Option('Choose VRAM',''));
  for(const t of [8,12,16,24,32,40,48,80])select.append(new Option(t+' GB',String(t)));
  const draft=modelVramDrafts.has(m.id)?modelVramDrafts.get(m.id):assigned;
  select.value=draft===null||draft===undefined?'':String(draft);
  controls.append(select);
  const save=button('Save VRAM',async()=>{if(!select.value)throw Error('Select a VRAM tier.');await saveModelVram(m,Number(select.value));});
  const updateSave=()=>{save.disabled=state.busy||state.demo||!select.value||Number(select.value)===assigned;};
  select.addEventListener('change',()=>{modelVramDrafts.set(m.id,select.value?Number(select.value):null);updateSave();});
  updateSave();controls.append(save);
  if(m.recommended_vram_gb){
   const applied=assigned===m.recommended_vram_gb;
   const accept=button(applied?'Recommended '+m.recommended_vram_gb+' GB applied':'Accept recommended '+m.recommended_vram_gb+' GB',async()=>{
    modelVramDrafts.delete(m.id);await saveModelVram(m,m.recommended_vram_gb);
   });
   accept.disabled=state.busy||state.demo||applied;controls.append(accept);
  }
  card.append(controls);
  if(m.errors.length)card.append(el('p',m.errors.join('; '),'error'));
  const d=el('details');d.append(el('summary','Files and discovery details'),el('pre',JSON.stringify({paths:m.paths,missing_shards:m.missing_shards},null,2)));card.append(d);list.append(card);
 }
 if(!state.models.length)list.append(el('article',state.state==='scanning'?'Scanning the selected models folder…':'No discovered models yet. Choose or rescan the active folder.'));
}
async function poll(){if(polling||!key)return;polling=true;try{render(await api('/api/state'));if($('login').open)$('login').close();}catch(e){$('connection').textContent='● Worker disconnected';}finally{polling=false;}}
async function loadTests(){if(state?.busy){$('test-list').replaceChildren(el('article','Test-file editing is available when the current operation has finished.'));return;}const data=await api('/api/tests');testData=data.tests;$('example-select').replaceChildren(...data.examples.map(x=>new Option(x,x)));const list=$('test-list');list.replaceChildren();for(const t of data.tests){const card=el('article');card.append(el('h3',t.name||t.id),el('p',t.id+' · '+t.variants.length+' workflow variants · '+(t.repetitions||1)+' repetition(s) · '+(t.enabled===false?'Disabled':'Enabled')));card.append(button('View / edit JSON',()=>openEditor(t)),el('p',t.variants.map(v=>v.id+' ('+v.steps.length+' top-level steps)').join(' · '),'muted'));list.append(card);}}
function openEditor(t){$('test-json').value=JSON.stringify(t,null,2);$('editor').showModal();}
async function loadResults(){if(state?.busy){$('result-list').replaceChildren(el('article','Stop or finish the active run before loading results from disk. Live progress remains available in Overview.'));return;}records=await api('/api/results');renderResults();}
function renderResults(){const search=$('result-filter').value.toLowerCase();const list=$('result-list');list.replaceChildren();for(const r of records.filter(r=>[r.model_id,r.test_id,r.variant_id].join(' ').toLowerCase().includes(search))){const card=el('article',undefined,'result-row');const title=el('div');title.append(el('b',r.model_id),el('p',r.test_id+' / '+r.variant_id,'muted'));const correct=r.score?.exact_match;let label=r.status!=='completed'?r.status:(correct===true?'PASS':correct===false?'FAIL':'NO EXACT ORACLE');if(r.measurement_valid===false&&r.status==='completed')label+=' · INVALID MEASUREMENT';label+=' · '+(r.execution_class||'legacy_unverified');card.append(title,el('span',label,correct===true?'success':'error'),el('span',typeof r.pipeline_seconds==='number'?r.pipeline_seconds.toFixed(3)+' s':'—'));const act=el('div',undefined,'actions');act.append(button('Inspect',()=>{$('result-json').textContent=JSON.stringify(r,null,2);$('inspect').showModal();}),button('Delete / rerun',async()=>{if(!confirm('Delete this result and make the case pending again? This action is recorded in the audit log.'))return;await api('/api/result/delete',{model_id:r.model_id,case_id:r.case_id});await loadResults();},'danger'));card.append(act);list.append(card);}if(!list.children.length)list.append(el('article','No matching result files.'));}
async function download(path,name){const blob=await api(path);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
on('login-submit',async()=>{key=$('login-key').value.trim();sessionStorage.setItem('rpg-worker-key',key);try{render(await api('/api/state'));$('login').close();}catch(e){$('login-error').textContent=e.message;}});
on('preflight',async()=>{await api('/api/preflight',{});await poll();});on('rescan',async()=>{await scanModelsInBackground();});on('run',async()=>{await api('/api/run',{});await poll();});
for(const [id,action] of [['pause','pause'],['resume','resume'],['stop-model','stop_after_model'],['stop','stop']])on(id,()=>api('/api/control',{action}));
on('prepare',()=>api('/api/preflight',{preparation:{gpu_name:$('target-name').value,vram_gb:Number($('target-tier').value)}}));
on('export',()=>download('/api/export','rpg-testing-evidence.zip'));on('unity-script',()=>download('/api/unity-script?tier='+$('target-tier').value,'rpg-unity-job.sh'));
on('refresh-tests',loadTests);on('refresh-results',loadResults);$('result-filter').addEventListener('input',renderResults);
on('import-example',async()=>{await api('/api/test/import-example',{id:$('example-select').value});render(await api('/api/state'));await loadTests();toast('Example added to test files.');});
on('new-test',()=>openEditor(testData[0]?{...testData[0],id:'new_test',name:'New test'}:{schema_version:2,id:'new_test',workflow:'steps',source:{},variants:[]}));
on('save-test',async()=>{let test;try{test=JSON.parse($('test-json').value);}catch{throw Error('This is not valid JSON.');}await api('/api/test/save',{test});$('editor').close();await loadTests();toast('Test validated and saved.');});
async function scanModelsInBackground(){await api('/api/models/scan',{});setPage('models');await poll();}
async function chooseModelsFolder(){
 folderChoosing=true;
 try{
  $('folder-onboarding').close();$('empty-folder').close();
  const picked=await api('/api/picker/models',{initial:$('model-root').value.trim()});
  if(picked.cancelled)return;
  $('model-root').value=picked.path;setupDirty=false;
  await api('/api/settings',{model_root:picked.path});
  toast('Models folder saved. Scanning it now…');
  await scanModelsInBackground();
 }finally{folderChoosing=false;}
}
async function chooseLlamaServer(){
 const picked=await api('/api/picker/llama',{initial:$('llama-path').value.trim()});
 if(picked.cancelled)return;
 $('llama-path').value=picked.path;setupDirty=false;
 await api('/api/settings',{llama_path:picked.path});await poll();toast('llama-server selected.');
}
on('save-setup',async()=>{const previousRoot=state.settings.model_root;const values={model_root:$('model-root').value.trim(),llama_path:$('llama-path').value.trim(),sync_source:$('sync-source').checked,publish_results:$('publish-results').checked};if($('api-token').value)values.hf_token=$('api-token').value;if(values.publish_results&&!state.settings.publish_results&&!confirm('Publish only synthetic safe-for-work results to the public GitHub repository? Do not enable for private data.'))return;await api('/api/settings',values);setupDirty=false;$('api-token').value='';toast('Worker setup saved.');if(values.model_root&&values.model_root!==previousRoot){toast('Models folder saved. Scanning it now…');await scanModelsInBackground();}else{await poll();}});
on('browse-models',chooseModelsFolder);on('browse-llama',chooseLlamaServer);
on('enable-remote',async()=>{const r=await api('/api/remote/enable',{});$('remote-url').textContent=r.url;toast('Private controller enabled. Pair your laptop at the displayed address.');});
on('disable-remote',async()=>{if(confirm('Disable remote access? A laptop connection will disconnect, but the local workbench stays available.'))await api('/api/remote/disable',{});});
on('pairing',async()=>{$('pairing-value').textContent=(await api('/api/pairing-key')).key;});
on('close-worker',async()=>{if(confirm('Close the worker service? Remote controls will stop working until it is started again.'))await api('/api/shutdown',{});});
on('restart',async()=>{await api('/api/restart',{});toast('Restarting with the latest code…');setTimeout(()=>location.reload(),2500);});


// Discovery and setup are UI-approved operations, never part of the unattended run.
let hubSignature='',runtimeSignature='',folderChoosing=false;
for(const tier of [8,12,16,24,32,40,48,80])$('hub-tier').append(new Option(tier+' GiB',String(tier)));
function folderPrompts(){
 if(!state||state.demo||state.busy||$('login').open||folderChoosing)return;
 const root=state.settings.model_root;
 if(!root){if(!$('folder-onboarding').open)$('folder-onboarding').showModal();return;}
 if($('folder-onboarding').open)$('folder-onboarding').close();
 if(state.folder_scanned&&!state.models.length&&state.settings.confirmed_empty_folder!==root){
  $('empty-folder-path').textContent=root;if(!$('empty-folder').open)$('empty-folder').showModal();
 }
}
async function pickFirstFolder(){setPage('setup');await chooseModelsFolder();}
on('onboarding-choose',pickFirstFolder);on('choose-different',pickFirstFolder);
on('accept-empty',async()=>{await api('/api/settings',{confirmed_empty_folder:state.settings.model_root});$('empty-folder').close();setPage('find');await poll();});
$('folder-onboarding').addEventListener('cancel',e=>{if(!state?.settings.model_root)e.preventDefault();});
on('hub-search',()=>{const query=$('hub-query').value.trim();return api(query.includes('/')?'/api/hub/inspect':'/api/hub/search',query.includes('/')?{repo_id:query,target_gb:Number($('hub-tier').value)}:{query});});
function renderHub(){
 const signature=JSON.stringify([state.hub_results,state.hub_detail]);if(signature===hubSignature)return;hubSignature=signature;
 const results=$('hub-results');results.replaceChildren();
 for(const row of state.hub_results||[]){const card=el('article');card.append(el('h3',row.id),el('p',(row.downloads??'—')+' downloads · '+(row.likes??'—')+' likes · license: '+(row.license||'See model card'),'muted'),button('View quantizations',()=>api('/api/hub/inspect',{repo_id:row.id,target_gb:Number($('hub-tier').value)})));results.append(card);}
 const detail=state.hub_detail;$('hub-variants-card').classList.toggle('hidden',!detail);if(!detail)return;
 $('hub-title').textContent=detail.repo_id;$('hub-license').textContent='Revision '+detail.revision.slice(0,12)+' · '+(detail.license||'Check publisher license')+' · '+detail.note;
 const list=$('hub-variants');list.replaceChildren();
 for(const v of detail.variants){const row=el('div',undefined,'quant-row'),label=el('label',undefined,'check'),check=el('input');check.type='checkbox';check.value=v.id;check.disabled=!v.complete;check.dataset.recommended=String(v.recommended);check.setAttribute('aria-label','Select '+v.quantization);label.append(check,el('b',v.quantization));row.append(label,el('span',v.size_bytes?(v.size_bytes/1e9).toFixed(2)+' GB · '+(v.size_bytes/2**30).toFixed(2)+' GiB':'Size unavailable'),el('span',v.shards+' file(s)'),el('span',(v.recommended?'Recommended · ':'')+v.fit_note,v.recommended?'success':'muted'));list.append(row);}
}
on('select-recommended',()=>{document.querySelectorAll('#hub-variants input').forEach(c=>c.checked=c.dataset.recommended==='true'&&!c.disabled);});
on('hub-download',async()=>{const ids=[...document.querySelectorAll('#hub-variants input:checked')].map(x=>x.value);if(!ids.length)throw Error('Select at least one quantization.');if(!state.settings.model_root)throw Error('Choose your models folder in Worker setup first.');if(!confirm('Download '+ids.length+' variant(s) into '+state.settings.model_root+'? No other model location will be used.'))return;await api('/api/hub/download',{ids,required_vram_gb:Number($('hub-tier').value)});});
on('runtime-list',()=>api('/api/runtime/list',{}));
function renderRuntimes(){
 $('runtime-installed').textContent=state.settings.llama_path||'No native runtime selected.';
 const signature=JSON.stringify(state.runtime_options);if(signature===runtimeSignature)return;runtimeSignature=signature;
 $('runtime-select').replaceChildren(...(state.runtime_options||[]).map(r=>new Option(r.tag+' · '+r.name+' · '+(r.size_bytes/1e6).toFixed(0)+' MB',r.id)));
 runtimeNote();
}
function runtimeNote(){const r=(state?.runtime_options||[]).find(r=>r.id===$('runtime-select').value);$('runtime-note').textContent=r?.note||'Refresh to browse compatible-platform releases. GPU compatibility is checked by preflight.';}
$('runtime-select').addEventListener('change',runtimeNote);
on('runtime-install',async()=>{const r=(state.runtime_options||[]).find(r=>r.id===$('runtime-select').value);if(!r)throw Error('Find and select a runtime release first.');if(confirm('Install '+r.name+' under this repository? This does not install or change GPU drivers.'))await api('/api/runtime/install',{id:r.id});});
on('runtime-locate',async()=>{setPage('setup');await chooseLlamaServer();});
async function loadAnalysis(){if(state?.busy){$('analysis-list').replaceChildren(el('article','Finish or stop the active operation before reading results.'));return;}const data=await api('/api/analysis');$('analysis-note').textContent=data.note;const list=$('analysis-list');list.replaceChildren();for(const g of data.groups){const card=el('article');card.append(el('h3',g.model_id+' · '+g.variant_id),el('span',(g.simulated?'SIMULATED · ':'')+g.execution_class,'badge'),el('p',g.test_id+' · '+g.scored+' scored · '+(g.exact_match_rate===null?'No exact score':(g.exact_match_rate*100).toFixed(1)+'% exact state matches')+' · median '+(g.median_pipeline_seconds===null?'—':g.median_pipeline_seconds.toFixed(3)+' s')),el('p',g.skipped+' skipped · '+g.infrastructure_errors+' errors · '+g.invalid_measurements+' invalid measurements','muted'));list.append(card);}if(!list.children.length)list.append(el('article','No recorded comparison groups yet.'));}
on('refresh-analysis',loadAnalysis);
if(!key)$('login').showModal();else poll();setInterval(poll,1200);
