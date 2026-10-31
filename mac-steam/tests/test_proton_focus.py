import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'runtime/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ProtonUpdates(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.library = base / 'Steam with spaces'
        self.proton = self.library / 'steamapps/common/Proton - Experimental'
        self.driver = self.proton / 'files/lib/wine/x86_64-unix/winex11.so'
        self.driver.parent.mkdir(parents=True)
        self.driver.write_bytes(b'valve driver')
        (self.proton / 'version').write_text('qualified build\n')
        companion = self.proton / 'files/lib/wine/x86_64-unix/ntdll.so'
        companion.write_bytes(b'qualified ABI')
        (self.library / 'steamapps/appmanifest_1493710.acf').write_text('"StateFlags" "4"')
        private = base / 'private/wine-focus'
        private.mkdir(parents=True)
        (private / 'winex11.so').write_bytes(b'fixed driver')
        (private / 'manifest.json').write_text(json.dumps({
            'original_sha256': sha(b'valve driver'), 'patched_sha256': sha(b'fixed driver'),
            'proton_version': 'qualified build',
            'companions': {'files/lib/wine/x86_64-unix/ntdll.so': sha(b'qualified ABI')},
        }))
        p = patch.object(prepare, 'PREFIX', private.parent)
        p.start()
        self.addCleanup(p.stop)

    def test_qualified_build_is_repaired_after_verification(self):
        seen = {}
        prepare.prepare_proton(self.library, seen)
        self.assertEqual(self.driver.read_bytes(), b'fixed driver')
        inode = self.driver.stat().st_ino
        prepare.prepare_proton(self.library, seen)
        self.assertEqual(self.driver.stat().st_ino, inode)
        self.driver.write_bytes(b'valve driver')
        prepare.prepare_proton(self.library, seen)
        self.assertEqual(self.driver.read_bytes(), b'fixed driver')
        self.assertEqual(self.driver.with_name('winex11.so.valve-original-focus').read_bytes(), b'valve driver')

    def test_download_and_running_proton_are_deferred(self):
        download = self.library / 'steamapps/downloading/1493710'
        download.mkdir(parents=True)
        prepare.prepare_proton(self.library, {})
        self.assertEqual(self.driver.read_bytes(), b'valve driver')
        download.rmdir()
        with patch.object(prepare, 'proton_in_use', return_value=True):
            prepare.prepare_proton(self.library, {})
        self.assertEqual(self.driver.read_bytes(), b'valve driver')
        prepare.prepare_proton(self.library, {})
        self.assertEqual(self.driver.read_bytes(), b'fixed driver')

    def test_unknown_abi_or_modified_driver_is_preserved(self):
        companion = self.proton / 'files/lib/wine/x86_64-unix/ntdll.so'
        companion.write_bytes(b'new ABI')
        prepare.prepare_proton(self.library, {})
        self.assertEqual(self.driver.read_bytes(), b'valve driver')
        companion.write_bytes(b'qualified ABI')
        self.driver.write_bytes(b'user modification')
        prepare.prepare_proton(self.library, {})
        self.assertEqual(self.driver.read_bytes(), b'user modification')

    def test_partial_update_restores_original_before_skipping(self):
        seen = {}
        prepare.prepare_proton(self.library, seen)
        (self.proton / 'version').write_text('new unqualified build')
        with patch.object(prepare, 'proton_in_use', return_value=True):
            prepare.prepare_proton(self.library, seen)
        self.assertEqual(self.driver.read_bytes(), b'fixed driver')
        prepare.prepare_proton(self.library, seen)
        self.assertEqual(self.driver.read_bytes(), b'valve driver')


if __name__ == '__main__':
    unittest.main()
