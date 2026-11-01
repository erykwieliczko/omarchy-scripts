#!/usr/bin/env python3
"""Check persistent CPU tuning, fallback isolation and boot selection failures."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('host_setup', Path(__file__).parents[1] / 'runtime/host-setup.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class HostSetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_cpu_policy_survives_module_load_and_does_not_break_fallback_driver(self):
        polling = self.root / 'sys/module/kvm/parameters/halt_poll_ns'
        polling.parent.mkdir(parents=True)
        polling.write_text('500000\n')
        host.tune(self.root)
        self.assertEqual(polling.read_text(), '0\n')
        options = (self.root / 'etc/modprobe.d/90-mac-steam-m3.conf').read_text()
        self.assertIn('halt_poll_ns=0', options)
        self.assertNotIn('options appledrm', options)
        service = (self.root / 'etc/systemd/system/mac-steam-m3-panel.service').read_text()
        self.assertIn('ConditionPathExists=/sys/module/appledrm/parameters/', service)
        self.assertIn('Before=display-manager.service', service)
        host.tune(self.root)

    def boot_fixture(self):
        defaults = self.root / 'etc/default/limine'
        defaults.parent.mkdir(parents=True)
        defaults.write_text('ESP_PATH="/boot/efi"\nKERNEL_CMDLINE[default]="root=UUID=FRESH-INSTALL rw"\nBOOT_ORDER="linux-aurora, *"\n')
        esp = self.root / 'boot/efi'
        (esp / 'EFI/Linux').mkdir(parents=True)
        config = esp / 'limine.conf'
        config.write_text('default_entry: Omarchy/linux-aurora\n/+Omarchy\n  //linux-aurora\n  path: original-fallback\n  //linux-aurora-dsc\n  cmdline: root=UUID=FRESH-INSTALL rw\n')
        module = self.root / f'usr/lib/modules/{host.RELEASE}/kernel/drivers/gpu/drm/apple/appledrm.ko'
        module.parent.mkdir(parents=True)
        module.write_bytes(b'qualified-module')
        # Minimal PE image; the extractor is stubbed independently below.
        data = bytearray(256)
        struct.pack_into('<I', data, 0x3c, 64)
        data[64:68] = b'PE\0\0'
        struct.pack_into('<H', data, 70, 1)
        struct.pack_into('<H', data, 84, 0)
        data[88:96] = b'.initrd\0'
        struct.pack_into('<IIII', data, 96, 4, 0, 4, 192)
        data[192:196] = b'test'
        (esp / 'EFI/Linux/omarchy_linux-aurora-dsc.efi').write_bytes(data)
        return defaults, config, module

    def test_selects_verified_kernel_preserves_root_arguments_and_fallback(self):
        defaults, config, module = self.boot_fixture()

        def extract(args, cwd, **kwargs):
            embedded = Path(cwd) / module.relative_to(self.root)
            embedded.parent.mkdir(parents=True)
            embedded.write_bytes(module.read_bytes())

        with patch.object(host, 'MODULE_SHA', hashlib.sha256(module.read_bytes()).hexdigest()), patch.object(host.subprocess, 'run', side_effect=extract):
            host.select_kernel(self.root)
            host.select_kernel(self.root)
        self.assertIn('default_entry: Omarchy/linux-aurora-dsc', config.read_text())
        self.assertIn('original-fallback', config.read_text())
        self.assertIn('root=UUID=FRESH-INSTALL rw', config.read_text())
        self.assertIn('root=UUID=FRESH-INSTALL rw', defaults.read_text())
        self.assertTrue(config.with_name('limine.conf.pre-mac-steam').exists())

    def test_wrong_module_never_changes_boot_selection(self):
        defaults, config, module = self.boot_fixture()
        before = defaults.read_bytes(), config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            host.select_kernel(self.root)
        self.assertEqual((defaults.read_bytes(), config.read_bytes()), before)

    def test_bad_embedded_module_never_changes_boot_selection(self):
        defaults, config, module = self.boot_fixture()
        before = defaults.read_bytes(), config.read_bytes()

        def extract(args, cwd, **kwargs):
            embedded = Path(cwd) / module.relative_to(self.root)
            embedded.parent.mkdir(parents=True)
            embedded.write_bytes(b'old-unfixed-driver')

        with patch.object(host, 'MODULE_SHA', hashlib.sha256(module.read_bytes()).hexdigest()), patch.object(host.subprocess, 'run', side_effect=extract):
            with self.assertRaisesRegex(ValueError, 'lacks the repaired'):
                host.select_kernel(self.root)
        self.assertEqual((defaults.read_bytes(), config.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
