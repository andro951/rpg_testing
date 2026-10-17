import hashlib,io,json,tarfile,tempfile,threading,unittest,zipfile
from pathlib import Path
from workbench.runtimes import automatic_bundle,bundles,extract_archive,install

class RuntimeTests(unittest.TestCase):
 def test_host_gpu_only(self):
  a=[{'id':i,'name':n,'size':10,'browser_download_url':'https://github.com/ggml-org/llama.cpp/releases/download/b1/'+n} for i,n in enumerate(['llama-b1-bin-win-cuda-12.4-x64.zip','cudart-llama-bin-win-cu12.4-x64.zip','llama-b1-bin-win-cpu-x64.zip','llama-b1-bin-ubuntu-vulkan-x64.tar.gz'])]
  b=bundles([{'tag_name':'b1','assets':a}],'Windows','AMD64');self.assertEqual(len(b),1);self.assertEqual(len(b[0]['assets']),2)
 def test_automatic_bundle_prefers_cuda12_for_gtx1080(self):
  choices=[{'id':'13','name':'llama-win-cuda-cu13-x64.zip','note':'CUDA 13','prerelease':False},
           {'id':'vk','name':'llama-win-vulkan-x64.zip','note':'Vulkan GPU build','prerelease':False},
           {'id':'12','name':'llama-win-cuda-cu12-x64.zip','note':'CUDA 12 candidate','prerelease':False}]
  self.assertEqual(automatic_bundle(choices,'NVIDIA GeForce GTX 1080')['id'],'12')
 def test_automatic_bundle_rejects_empty_results(self):
  with self.assertRaises(ValueError):automatic_bundle([],'GTX 1080')
 def test_bad_archive_paths(self):
  for name in ['../bad','/etc/file','C:/x','a\\b']:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'a.zip'
    with zipfile.ZipFile(p,'w') as z:
     # ZipInfo normally normalizes backslashes on Windows. Write the exact hostile
     # archive spelling so the test exercises the extractor, not the ZIP builder.
     info=zipfile.ZipInfo('safe');info.filename=name
     z.writestr(info,b'bad')
    with self.assertRaises(ValueError):extract_archive(p,Path(d)/'out')
 def test_extraction_budget(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('large',b'x'*100)
   with self.assertRaises(ValueError):extract_archive(p,Path(d)/'out',10)
 def test_manual_install_and_hash_check(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('llama-server.exe',b'fake-not-executed')
  data=b.getvalue();asset={'name':'runtime.zip','size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest(),'browser_download_url':'https://github.com/ggml-org/llama.cpp/releases/download/b1/runtime.zip'}
  with tempfile.TemporaryDirectory() as d:
   bundle={'id':'abc','tag':'b1','assets':[asset]};root=Path(d)
   path=Path(install(bundle,root,threading.Event(),lambda *a:None,lambda *a,**k:io.BytesIO(data)))
   self.assertTrue(path.is_relative_to(root));self.assertTrue(path.is_file())
   self.assertEqual(install(bundle,root,threading.Event(),lambda *a:None),str(path))
   path.write_bytes(b'tampered')
   with self.assertRaises(ValueError):install(bundle,root,threading.Event(),lambda *a:None)
 def test_bad_publisher_checksum_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   data=b'abc';asset={'name':'bad.zip','size':3,'digest':'sha256:'+'0'*64,'browser_download_url':'https://github.com/ggml-org/llama.cpp/releases/download/b1/bad.zip'}
   with self.assertRaises(ValueError):install({'id':'a','tag':'b1','assets':[asset]},Path(d),threading.Event(),lambda *a:None,lambda *a,**k:io.BytesIO(data))
   self.assertFalse(any(p.name=='llama-server.exe' for p in Path(d).rglob('*')))

if __name__=='__main__':unittest.main()
