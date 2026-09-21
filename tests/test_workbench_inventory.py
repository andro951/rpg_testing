import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.inventory import *


def fake_gguf(path, name='Example'):
    def st(s):
        b=s.encode();return struct.pack('<Q',len(b))+b
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,2)+st('general.name')+struct.pack('<I',8)+st(name)+st('qwen.context_length')+struct.pack('<II',4,32768))

class InventoryTests(unittest.TestCase):
    def test_reads_settings_not_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);p=home/'.lmstudio/settings.json';p.parent.mkdir();p.write_text(json.dumps({'modelsDirectory':str(home/'custom')}))
            self.assertEqual(lmstudio_folder(home)['path'],str(home/'custom'))
    def test_no_guessed_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);(home/'.lmstudio/models').mkdir(parents=True)
            self.assertIsNone(lmstudio_folder(home)['path'])
    def test_corrupt_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'.lmstudio/settings.json';p.parent.mkdir();p.write_text('{')
            self.assertIsNone(lmstudio_folder(Path(tmp))['path'])
    def test_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.gguf';fake_gguf(p)
            self.assertEqual(gguf_metadata(p)['qwen.context_length'],32768)
    def test_reject_bad_gguf(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.gguf';p.write_bytes(b'bad')
            with self.assertRaises(ValueError):gguf_metadata(p)
    def test_scan_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'author/repo/Model-Q4_K_M.gguf';fake_gguf(p)
            catalog=[{'id':'m','files':[p.name],'required_vram_gb':8}]
            out=scan_models(Path(tmp),catalog,[{'key':'author/repo@q4_k_m','path':str(p)}])
            self.assertEqual(out[0]['id'],'m');self.assertTrue(out[0]['complete']);self.assertEqual(out[0]['model_key'],'author/repo@q4_k_m')
    def test_split_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model-Q4_K_M-00001-of-00002.gguf';fake_gguf(p)
            out=scan_models(Path(tmp),[]);self.assertFalse(out[0]['complete']);self.assertEqual(len(out[0]['missing_shards']),1)
    def test_projector_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_gguf(Path(tmp)/'mmproj-model.gguf');self.assertEqual(scan_models(Path(tmp),[]),[])
    def test_file_hash_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.gguf';fake_gguf(p);a=file_hashes([str(p)]);fake_gguf(p,'Changed');self.assertNotEqual(a,file_hashes([str(p)]))
    def test_gpu_visibility(self):
        raw='0, GPU-a, GTX 1080, 8192, 8000, 550\n1, GPU-b, A100, 81920, 80000, 550'
        with patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'GPU-b'}):
            self.assertEqual(detect_gpus(lambda args:raw)[0]['name'],'A100')
    def test_auto_context(self):
        out=automatic_context([{'source':{'x':'hello'},'variants':[{'steps':[]}]}],{'a.context_length':8192})
        self.assertEqual(out['allocated_tokens'],4096);self.assertIsNone(out['output_cap'])
    def test_no_unknown_context_guess(self):
        with self.assertRaises(ValueError):automatic_context([],{})

if __name__=='__main__':unittest.main()
