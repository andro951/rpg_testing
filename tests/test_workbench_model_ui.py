import io,json,shutil,struct,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import read_json,write_json
from workbench.hub import group_variants
from workbench.analysis import summarize

ROOT=Path(__file__).resolve().parents[1]
class ModelUiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'repository';self.root.mkdir()
  shutil.copytree(ROOT/'test_specs',self.root/'test_specs');write_json(self.root/'models.json',[])
  self.models=Path(self.tmp.name)/'chosen-models';self.models.mkdir()
  self.app=Controller(self.root);self.app.settings['sync_source']=False;self.app.selftest=lambda:None
 def test_storage_starts_none_no_inferred_root(self):
  self.assertEqual(self.app.settings['model_root'],'');self.assertIsNone(self.app.folder_info()['path'])
  self.assertFalse(list(self.root.rglob('*.gguf')))
 def test_migration_drops_old_automatic_folder(self):
  write_json(self.app.settings_path,{'backend':'lmstudio','model_root':'C:/old-auto','lms_path':'x'})
  app=Controller(self.root);self.assertEqual(app.settings['backend'],'llamacpp');self.assertEqual(app.settings['model_root'],'');self.assertNotIn('lms_path',app.settings)
 def test_explicit_empty_folder_confirmation(self):
  self.app.configure({'model_root':str(self.models)})
  self.assertTrue(self.app.folder_scanned);self.assertEqual(self.app.last_models,[])
  self.assertNotEqual(self.app.settings['confirmed_empty_folder'],str(self.models))
  self.app.configure({'confirmed_empty_folder':str(self.models)})
  self.app.configure({'model_root':str(self.models)})
  self.assertEqual(self.app.settings['confirmed_empty_folder'],str(self.models))
 def test_search_does_not_download(self):
  with patch('workbench.hub.HubClient.search',return_value=[{'id':'author/model'}]) as mock,patch('workbench.downloads.download_model') as download:
   self.app.search_hub({'query':'Qwen'});mock.assert_called_once_with('Qwen');download.assert_not_called()
  self.assertEqual(self.app.hub_results,[{'id':'author/model'}])
 def test_token_never_exposed(self):
  self.app.configure({'hf_token':'SECRET'})
  self.assertNotIn('SECRET',json.dumps(self.app.snapshot()));self.app.log('test','SECRET')
  self.assertNotIn('SECRET',json.dumps(self.app.snapshot()))
 def test_download_selection_requires_browsed_id(self):
  self.app.configure({'model_root':str(self.models)})
  self.app.hub_detail={'variants':[]}
  with self.assertRaises(ValueError):self.app.download_selected({'ids':['madeup'],'required_vram_gb':8})
 def test_model_download_and_registration(self):
  self.app.configure({'model_root':str(self.models)})
  self.app.hub_detail=group_variants({'id':'a/b','sha':'a'*40,'siblings':[{'rfilename':'m-Q4_K_M.gguf','size':24}]},8)
  variant=self.app.hub_detail['variants'][0]
  def download(model,root,*a,**k):
   f=root/model['files'][0];f.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0));return [str(f)]
  with patch('workbench.downloads.download_model',side_effect=download):self.app.download_selected({'ids':[variant['id']],'required_vram_gb':8})
  model=self.app.catalog()[0];self.assertEqual(model['required_vram_gb'],8);self.assertEqual(len(model['sha256']['m-Q4_K_M.gguf']),64)
  self.assertTrue((self.models/'m-Q4_K_M.gguf').exists());self.assertFalse(list(self.root.rglob('*.gguf')))
 def test_analysis_never_combines_gpu_and_hybrid(self):
  a={'case_id':'a','status':'completed','model_id':'m','execution_class':'full_gpu','pipeline_seconds':1,'score':{'exact_match':True}}
  b={**a,'case_id':'b','execution_class':'cpu_offloaded','pipeline_seconds':100}
  report=summarize([a,b]);self.assertEqual(len(report['groups']),2)
  self.assertEqual({g['execution_class'] for g in report['groups']},{'full_gpu','cpu_offloaded'})
 def test_skipped_not_inaccuracy_denominator(self):
  result=summarize([{'case_id':'a','model_id':'m','status':'skipped','execution_class':'full_gpu','score':{'exact_match':None}}])
  g=result['groups'][0];self.assertEqual(g['skipped'],1);self.assertIsNone(g['exact_match_rate'])

if __name__=='__main__':unittest.main()
