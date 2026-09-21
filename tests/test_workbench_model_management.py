"""Folder consent, browser-action contracts, verified downloads and cache-free storage."""
import copy
import hashlib
import io
import json
import os
import shutil
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import read_json,write_json
from workbench.downloads import download_model
from workbench.hub import HubClient,group_variants
from workbench.inventory import scan_models

ROOT=Path(__file__).resolve().parents[1]
DATA=b'GGUF'+struct.pack('<IQQ',3,0,0)

class ModelManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'repository';self.root.mkdir()
        self.models=self.base/'chosen-models';self.models.mkdir()
        write_json(self.root/'models.json',[])
        self.app=Controller(self.root);self.app.configure({'sync_source':False})
    def selection(self):
        return group_variants({'id':'publisher/example','sha':'a'*40,'siblings':[{
            'rfilename':'Model-Q4_K_M.gguf','size':len(DATA),
            'lfs':{'sha256':hashlib.sha256(DATA).hexdigest(),'size':len(DATA)}}]},8)
    def test_first_launch_has_no_model_root_or_autodiscovery(self):
        self.assertEqual(self.app.settings['model_root'],'')
        self.assertIsNone(self.app.folder_info()['path'])
        self.assertFalse(self.app.folder_scanned)
        self.assertFalse((self.root/'models').exists())
    def test_old_settings_do_not_implicitly_authorize_directory(self):
        write_json(self.app.settings_path,{'backend':'lmstudio','model_root':str(self.models),'confirmed_empty_folder':str(self.models)})
        app=Controller(self.root)
        self.assertEqual(app.settings['model_root'],'');self.assertEqual(app.settings['backend'],'llamacpp')
    def test_selected_empty_folder_needs_confirmation_and_persists(self):
        self.app.configure({'model_root':str(self.models)})
        self.assertFalse(self.app.folder_scanned)
        self.app.scan_folder()
        self.assertTrue(self.app.folder_scanned);self.assertEqual(self.app.last_models,[])
        self.assertNotEqual(self.app.settings['confirmed_empty_folder'],str(self.models))
        self.app.configure({'confirmed_empty_folder':str(self.models)})
        again=Controller(self.root)
        self.assertEqual(again.settings['model_root'],str(self.models.resolve()))
        self.assertEqual(again.settings['confirmed_empty_folder'],str(self.models.resolve()))
    def test_confirmation_cannot_authorize_different_folder(self):
        self.app.configure({'model_root':str(self.models)})
        other=self.base/'other';other.mkdir()
        with self.assertRaises(ValueError):self.app.configure({'confirmed_empty_folder':str(other)})
        self.assertEqual(self.app.settings['confirmed_empty_folder'],'')
    def test_selecting_other_folder_resets_confirmation(self):
        self.app.configure({'model_root':str(self.models),'confirmed_empty_folder':str(self.models)})
        other=self.base/'other';other.mkdir();self.app.configure({'model_root':str(other)})
        self.assertEqual(self.app.settings['confirmed_empty_folder'],'')
    def test_existing_model_is_discovered_without_copy(self):
        path=self.models/'existing.gguf';path.write_bytes(DATA)
        self.app.configure({'model_root':str(self.models)})
        self.app.scan_folder()
        self.assertEqual(len(self.app.last_models),1)
        self.assertEqual([Path(p).resolve() for p in self.app.last_models[0]['paths']],[path.resolve()])
        self.assertEqual(list(self.root.rglob('*.gguf')),[])
    def test_saving_model_root_does_not_hold_settings_request_for_scan(self):
        with patch.object(self.app,'scan_folder',side_effect=AssertionError('scan must be separate')):
            self.app.configure({'model_root':str(self.models)})
        self.assertEqual(self.app.settings['model_root'],str(self.models.resolve()))
        self.assertFalse(self.app.folder_scanned)
    def test_manager_download_requires_folder(self):
        self.app.hub_detail=self.selection()
        with patch('workbench.downloads.download_model') as fn:
            with self.assertRaises(ValueError):self.app.download_selected({'ids':[self.app.hub_detail['variants'][0]['id']],'required_vram_gb':8})
            fn.assert_not_called()
    def test_manager_fetch_installs_in_approved_root_and_catalogs(self):
        self.app.configure({'model_root':str(self.models)})
        self.app.hub_detail=self.selection();variant=self.app.hub_detail['variants'][0]
        def opener(*a,**k):
            response=io.BytesIO(DATA);response.headers={'Content-Length':str(len(DATA))};return response
        def download(model,root,cancel,log,**kwargs):return download_model(model,root,cancel,log,opener=opener,**kwargs)
        with patch('workbench.downloads.download_model',side_effect=download):
            self.app.download_selected({'ids':[variant['id']],'required_vram_gb':8})
        p=self.models/'publisher/example'/('a'*12)/'Model-Q4_K_M.gguf'
        self.assertEqual(p.read_bytes(),DATA);self.assertEqual(list(self.root.rglob('*.gguf')),[])
        self.assertEqual(self.app.catalog()[0]['sha256'],variant['sha256'])
        self.assertEqual(self.app.last_models[0]['required_vram_gb'],8)
    def test_no_stale_selection_downloads(self):
        self.app.configure({'model_root':str(self.models)});self.app.hub_detail=self.selection()
        with patch('workbench.downloads.download_model') as fn:
            with self.assertRaises(ValueError):self.app.download_selected({'ids':['not-approved'],'required_vram_gb':8})
            fn.assert_not_called()
    def test_demo_never_installs_real_models_or_runtime(self):
        demo=Controller(self.root,True)
        with self.assertRaises(ValueError):demo.download_selected({'ids':['x'],'required_vram_gb':8})
        with self.assertRaises(ValueError):demo.install_runtime({'id':'x'})
    def test_resumed_bytes_stay_in_selected_root(self):
        m=self.selection()['variants'][0];folder=self.models/'publisher/example'/('a'*12);folder.mkdir(parents=True)
        partial=folder/'Model-Q4_K_M.gguf.partial';partial.write_bytes(DATA[:10])
        def opener(req,**kwargs):
            self.assertEqual(req.get_header('Range'),'bytes=10-')
            response=io.BytesIO(DATA[10:]);response.status=206
            response.headers={'Content-Length':str(len(DATA)-10),'Content-Range':f'bytes 10-{len(DATA)-1}/{len(DATA)}'}
            return response
        download_model(m,self.models,threading.Event(),opener=opener)
        self.assertFalse(partial.exists());self.assertEqual((folder/'Model-Q4_K_M.gguf').read_bytes(),DATA)
    def test_catalog_path_disambiguates_equal_names(self):
        a=self.models/'first/model'/('a'*12)/'model.gguf';b=self.models/'second/model'/('b'*12)/'model.gguf'
        for p in [a,b]:p.parent.mkdir(parents=True);p.write_bytes(DATA)
        catalog=[{'id':'first','repo_id':'first/model','revision':'a'*40,'files':['model.gguf'],'required_vram_gb':8},
                 {'id':'second','repo_id':'second/model','revision':'b'*40,'files':['model.gguf'],'required_vram_gb':8}]
        found=scan_models(self.models,catalog)
        self.assertEqual([x['id'] for x in found],['first','second']);self.assertFalse(any(x['errors'] for x in found))
    def test_runtime_repair_requires_server_issued_selection(self):
        with patch('workbench.runtimes.install') as install:
            with self.assertRaises(ValueError):self.app.install_runtime({'id':'arbitrary-url'})
            install.assert_not_called()

if __name__=='__main__':unittest.main()
