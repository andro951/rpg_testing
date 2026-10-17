"""GUI-approved model discovery/downloads and native-runtime installation."""
from __future__ import annotations
import copy
from pathlib import Path
from .domain import TIERS,write_json
from .inventory import scan_models
from .planning import validate_catalog
from .workflows import Cancelled

class ModelManager:
    def reconcile_installed_catalog(self,found):
        """Forget catalog/artifact entries whose GGUFs are no longer installed.

        The caller must only use this after a successful scan of an existing
        configured model directory. Historical benchmark results are evidence
        and are intentionally retained.
        """
        if self.demo:return []
        catalog=self.catalog()
        if not catalog:return []
        present={item['id'] for item in found if item.get('catalogued')}
        removed=[model['id'] for model in catalog if model['id'] not in present]
        if not removed:return []
        kept=[model for model in catalog if model['id'] in present]
        validate_catalog(kept);write_json(self.root/'models.json',kept)
        registry_changed=False
        for mid in removed:
            if mid in self.registry:
                self.registry.pop(mid,None);registry_changed=True
        if registry_changed:write_json(self.registry_path,self.registry)
        self.report=None
        self.log('catalog_cleanup','Removed missing installed model metadata: '+', '.join(removed))
        return removed

    def search_hub(self,payload):
        from .hub import HubClient
        self.hub_results=HubClient(self.settings.get('hf_token','')).search(payload['query'])
        self.message=f'Found {len(self.hub_results)} GGUF repositories. Open one to view quantizations.'
    def inspect_hub(self,payload):
        from .hub import HubClient
        self.hub_detail=HubClient(self.settings.get('hf_token','')).variants(payload['repo_id'],payload.get('target_gb',8))
        self.message='Quantizations loaded from a pinned repository revision.'
    def download_selected(self,payload):
        if self.demo:raise ValueError('Demo mode never installs real models. Open the normal Workbench launcher.')
        from .downloads import download_model
        root=Path(self.settings.get('model_root',''))
        if not self.settings.get('model_root') or not root.is_absolute() or not root.is_dir():
            raise ValueError('Choose an existing models folder first. No default is created.')
        if not self.hub_detail:raise ValueError('Browse a repository first')
        ids=payload.get('ids');tier=payload.get('required_vram_gb')
        if not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids) or len(ids)!=len(set(ids)):
            raise ValueError('Select one or more quantizations')
        if type(tier)is not int or tier not in TIERS:raise ValueError('Select a VRAM assignment for the variants')
        options={m['id']:m for m in self.hub_detail['variants']}
        if any(i not in options or not options[i]['complete'] for i in ids):raise ValueError('Stale or incomplete selection')
        catalog=self.catalog()
        for mid in ids:
            if self.cancel_event.is_set():raise Cancelled('Download cancelled')
            model=copy.deepcopy(options[mid]);model.update(required_vram_gb=tier,vram_status='user_assigned_unverified')
            for key in ('recommended','fit_note'):model.pop(key,None)
            catalog=[m for m in catalog if m['id']!=mid]+[model]
            validate_catalog(catalog);write_json(self.root/'models.json',catalog)
            self.message='Downloading '+model['quantization']+' into '+str(root)
            download_model(model,root,self.cancel_event,self.log,token=self.settings.get('hf_token',''))
            self.log('download','Verified '+mid)
        self.scan_folder();self.report=None
        self.message='Models installed and verified. Run preflight next.'
    def repair_runtime(self,gpu_name=''):
        if self.demo:raise ValueError('Demo mode never installs runtimes. Open the normal Workbench launcher.')
        from .runtimes import RuntimeClient,automatic_bundle
        self.runtime_options=RuntimeClient().releases()
        choice=automatic_bundle(self.runtime_options,gpu_name)
        self.log('runtime','User approved automatic runtime repair; selected '+choice['tag']+' / '+choice['name'])
        self.message='Installing official llama.cpp runtime: '+choice['name']
        self.install_runtime({'id':choice['id']})
        return choice
    def list_runtimes(self):
        from .runtimes import RuntimeClient
        self.runtime_options=RuntimeClient().releases();self.message='Select an official build to install it.'
    def install_runtime(self,payload):
        if self.demo:raise ValueError('Demo mode never installs runtimes. Open the normal Workbench launcher.')
        from .runtimes import install
        from .native import capabilities
        choice=next((b for b in self.runtime_options if b['id']==payload.get('id')),None)
        if choice is None:raise ValueError('Refresh available runtimes before installing')
        path=install(choice,self.root,self.cancel_event,self.log)
        capabilities(path,preparation=True)
        self.settings['llama_path']=path;self.save_settings();self.version_cache=None;self.report=None
        self.message='Runtime installed under the repository. Preflight will check the actual GPU.'
