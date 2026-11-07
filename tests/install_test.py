"""验证安装边界、升级备份与旧文件清理。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALL = Path(__file__).resolve().parents[1] / 'scripts/install.py'

class InstallTests(unittest.TestCase):
    def test_install_and_upgrade(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            mods = base / 'Mods'
            other = mods / 'other-mod'
            other.mkdir(parents=True)
            (other / 'keep.txt').write_text('不修改')
            def run():
                return subprocess.run([sys.executable, str(INSTALL), '--mods-dir', str(mods)], capture_output=True)
            self.assertEqual(run().returncode, 0)
            target = mods / 'balatro-assistant'
            self.assertFalse((target / 'tests').exists())
            self.assertIn('MIT License', (target / 'LICENSE').read_text())  # MIT 要求副本附带许可证
            (target / 'obsolete.lua').write_text('旧文件')
            self.assertEqual(run().returncode, 0)
            self.assertFalse((target / 'obsolete.lua').exists())
            self.assertEqual((other / 'keep.txt').read_text(), '不修改')
            backups = list((base / 'assistant-backups').iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / 'obsolete.lua').read_text(), '旧文件')

    def test_refuse_foreign_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'Mods/balatro-assistant'
            target.mkdir(parents=True)
            manifest = target / 'balatro-assistant.json'
            manifest.write_text(json.dumps({'id': 'someone_else'}))
            result = subprocess.run([sys.executable, str(INSTALL), '--mods-dir', str(target.parent)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(manifest.read_text())['id'], 'someone_else')

if __name__ == '__main__':
    unittest.main()
