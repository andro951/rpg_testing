"""GUI actions for explicitly selected models and native runtime installations."""
from __future__ import annotations
import copy
from pathlib import Path
from .domain import TIERS,write_json
from .inventory import file_hashes,scan_models
from .planning import validate_catalog
from .workflows import Cancelled

class ModelManager:
    def search_hub(self,payload):
        from .hub import HubClient
        self.hub_results=HubClient(self.settings.get('hf_token','')).search(payload['query'])
        self.message=f'Found {len(self.hub_results)} GGUF repositories. Open one to browse quantizations.'
    def inspect_hub(self,payload):
        from .hub import HubClient
        self.hub_detail=HubClient(self.settings.get('hf_token','')).variants(payload['repo_id'],payload.get('target_gb',8))
        self.message='Available quantizations loaded from the pinned repository revision.'
    def download_selected(self,payload):
        from .downloads import download_model
        if not self.settings.get('model_root'):raise ValueError('Choose your models folder first. No default folder is created.')
        root=Path(self.settings['model_root'])
        if not root.is_dir():raise ValueError('The selected models folder is no longer available')
        if not self.hub_detail:raise ValueError('Browse a repository first')
        selected=payload.get('ids',[]);tier=payload.get('required_vram_gb')
        if not isinstance(selected,list) or not selected or any(not isinstance(s,str) for s in selected) or len(selected)!=len(set(selected)):raise ValueError('Select one or more quantizations')
        if type(tier)is not int or tier not in TIERS:raise ValueError('Choose the VRAM tier for the selected variants')
        options={m['id']:m for m in self.hub_detail['variants']}
        if any(mid not in options or not options[mid]['complete'] for mid in selected):raise ValueError('A selection is stale or incomplete')
        catalog=self.catalog()
        for mid in selected:
            if self.cancel_event.is_set():raise Cancelled('Downloads cancelled')
            model=copy.deepcopy(options[mid]);model['required_vram_gb']=tier;model['vram_status']='user_assigned_unverified'
            model.pop('recommended',None);model.pop('fit_note',None)
            old=next((m for m in catalog if m['id']==mid),None)
            if old:catalog.remove(old)
            catalog.append(model);validate_catalog(catalog);write_json(self.root/'models.json',catalog)
            self.message='Downloading '+model['quantization']+' directly into '+str(root)
            paths=download_model(model,root,self.cancel_event,self.log,token=self.settings.get('hf_token',''))
            model['sha256']=file_hashes(paths);write_json(self.root/'models.json',catalog)
            self.log('download','Verified and installed '+mid)
        self.last_models=scan_models(root,catalog);self.folder_scanned=True;self.report=None
        self.message='Downloads verified. Run preflight to prepare your tests.'
    def list_runtimes(self):
        from .runtimes import RuntimeClient
        self.runtime_options=RuntimeClient().releases()
        self.message='Official runtime releases loaded. Select a build to install it.'
    def install_runtime(self,payload):
        from .runtimes import install
        from .native import capabilities
        chosen=next((b for b in self.runtime_options if b['id']==payload.get('id')),None)
        if not chosen:raise ValueError('Refresh runtime releases before choosing a build')
        path=install(chosen,self.root,self.cancel_event,self.log)
        capabilities(path,preparation=True)
        self.settings['llama_path']=path;self.save_settings();self.version_cache=None;self.report=None
        self.message='Runtime installed under the repository. Run preflight to verify the assigned GPU.'
