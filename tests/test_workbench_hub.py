import copy,io,json,struct,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.hub import group_variants,HubClient,safe_remote_file,SecureRedirect
from workbench.downloads import download_model,hash_file
from workbench.workflows import Cancelled

class Response(io.BytesIO):
    def __init__(self,data,status=200,headers=None):super().__init__(data);self.status=status;self.headers=headers or {'Content-Length':str(len(data))}

def gguf():return b'GGUF'+struct.pack('<IQQ',3,0,0)
def info():
    return {'id':'author/model','sha':'a'*40,'cardData':{'license':'apache-2.0'},'siblings':[
        {'rfilename':'weights/Model-Q5_K_M.gguf','size':6470000000},
        {'rfilename':'Model-Q4_K_M.gguf','size':5630000000},
        {'rfilename':'Model-Q4_K_S.gguf','size':5400000000},
        {'rfilename':'Model-Q8_0.gguf','size':9800000000}]}

class HubTests(unittest.TestCase):
    def test_quant_browser_and_recommendations(self):
        result=group_variants(info(),8);items=result['variants']
        self.assertEqual({x['quantization'] for x in items},{'Q5_K_M','Q4_K_M','Q4_K_S','Q8_0'})
        self.assertEqual([x['quantization'] for x in items if x['recommended']],['Q5_K_M','Q4_K_M'])
        self.assertEqual(items[1]['revision'],'a'*40)
    def test_split_group_complete(self):
        data=info();data['siblings']=[{'rfilename':f'M-Q4_K_M-{i:05}-of-00002.gguf','size':100} for i in (1,2)]
        items=group_variants(data,8)['variants'];self.assertEqual(len(items),1);self.assertEqual(items[0]['size_bytes'],200);self.assertTrue(items[0]['complete'])
        data['siblings'].pop();self.assertFalse(group_variants(data,8)['variants'][0]['complete'])
    def test_no_fake_revision_or_unsafe_paths(self):
        data=info();data['sha']='main'
        with self.assertRaises(ValueError):group_variants(data,8)
        for name in ['../x.gguf','C:/x.gguf','/x.gguf','a\\x.gguf','a//x.gguf']:
            with self.assertRaises(ValueError):safe_remote_file(name)
    def test_metadata_search_no_files_written(self):
        seen=[]
        def opener(request,**kw):seen.append(request);return Response(json.dumps([{'id':'a/b','downloads':1}]).encode())
        result=HubClient(opener=opener).search('Qwen 9B')
        self.assertEqual(result[0]['id'],'a/b');self.assertIn('filter=gguf',seen[0].full_url)
    def test_download_only_selected_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            m={'repo_id':'a/b','revision':'a'*40,'files':['m.gguf']}
            paths=download_model(m,Path(tmp),threading.Event(),opener=lambda *a,**k:Response(gguf()))
            self.assertTrue(Path(paths[0]).is_relative_to(Path(tmp)));self.assertEqual(Path(paths[0]).read_bytes(),gguf())
    def test_resume_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'a/b'/('a'*12);dest.mkdir(parents=True);(dest/'m.gguf.partial').write_bytes(gguf()[:10])
            def opener(request,**kw):
                self.assertEqual(request.headers['Range'],'bytes=10-')
                return Response(gguf()[10:],206,{'Content-Range':f'bytes 10-{len(gguf())-1}/{len(gguf())}'})
            download_model({'repo_id':'a/b','revision':'a'*40,'files':['m.gguf']},root,threading.Event(),opener=opener)
            self.assertEqual((dest/'m.gguf').read_bytes(),gguf())
    def test_bad_range_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):download_model({'repo_id':'a/b','files':['m.gguf']},Path(tmp),threading.Event(),opener=lambda *a,**k:Response(gguf(),206,{'Content-Range':'bytes 9-10/11'}))
    def test_checksum_failure_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):download_model({'repo_id':'a/b','files':['m.gguf'],'sha256':{'m.gguf':'0'*64}},Path(tmp),threading.Event(),opener=lambda *a,**k:Response(gguf()))
            self.assertFalse(list(Path(tmp).rglob('m.gguf')))
    def test_no_root_default(self):
        with self.assertRaises(ValueError):download_model({'repo_id':'a/b','files':['m.gguf']},'',threading.Event())
    def test_cancel_preserves_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            event=threading.Event()
            class Cancelling(Response):
                def read(self,n):event.set();return super().read(n)
            with self.assertRaises(Cancelled):download_model({'repo_id':'a/b','files':['m.gguf']},Path(tmp),event,opener=lambda *a,**kw:Cancelling(gguf()))
            self.assertTrue(list(Path(tmp).rglob('*.partial')));self.assertFalse(list(Path(tmp).rglob('m.gguf')))

if __name__=='__main__':unittest.main()
