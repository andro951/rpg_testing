import tempfile
import unittest
from pathlib import Path
from workbench import native_dialog

class NativeDialogTests(unittest.TestCase):
    def test_initial_directory_uses_existing_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(Path(native_dialog._initial(temp)).resolve(),Path(temp).resolve())
    def test_initial_file_uses_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'llama-server.exe';p.write_bytes(b'x')
            self.assertEqual(Path(native_dialog._initial(str(p))).resolve(),Path(temp).resolve())
    def test_missing_initial_does_not_invent_a_directory(self):
        self.assertIsNone(native_dialog._initial('/definitely/not/a/real/workbench/path'))

if __name__=='__main__':unittest.main()
