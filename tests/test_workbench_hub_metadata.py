import unittest
from workbench.hub import group_variants,safe_remote_file

class HubMetadataTests(unittest.TestCase):
    def test_group_and_rank(self):
        info={'id':'a/b','sha':'a'*40,'siblings':[{'rfilename':'M-Q5_K_M.gguf','size':6470000000},{'rfilename':'M-Q4_K_M.gguf','size':5630000000},{'rfilename':'M-Q4_K_S.gguf','size':5400000000}]}
        result=group_variants(info,8)
        self.assertEqual([x['quantization'] for x in result['variants'] if x['recommended']],['Q5_K_M','Q4_K_M'])
    def test_requires_immutable_revision(self):
        with self.assertRaises(ValueError):group_variants({'id':'a/b','sha':'main'},8)
    def test_no_unsafe_file_paths(self):
        for path in ['../file.gguf','/etc/a.gguf','C:/x.gguf','a\\x.gguf']:
            with self.assertRaises(ValueError):safe_remote_file(path)
    def test_all_shards_required(self):
        info={'id':'a/b','sha':'b'*40,'siblings':[{'rfilename':'M-Q4_K_M-00001-of-00002.gguf','size':100}]}
        self.assertFalse(group_variants(info,8)['variants'][0]['complete'])

if __name__=='__main__':unittest.main()
