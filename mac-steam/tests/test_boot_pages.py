"""Check persistent source arguments, regenerated UKIs and failed-build recovery."""
import gzip
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('boot_pages', Path(__file__).parents[1] / 'runtime/boot-pages.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def uki(cmdline):
    content = cmdline.encode() + b'\0'
    data = bytearray(192 + len(content))
    struct.pack_into('<I', data, 0x3c, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<H', data, 70, 1)
    data[88:96] = b'.cmdline'
    struct.pack_into('<IIII', data, 96, len(content), 0, len(content), 192)
    data[192:] = content
    return data


class MixedPageBoot(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.grub = self.make('etc/default/grub',
            'GRUB_CMDLINE_LINUX="rd.luks.name=FRESH-UUID=root rootflags=subvol=@ user4k=off"\n'
            "GRUB_CMDLINE_LINUX_DEFAULT='quiet splash user4k=0' # owner comment\n")
        self.limine = self.make('etc/default/limine', 'ESP_PATH="/boot/efi"\nKERNEL_CMDLINE[default]="old"\n')
        self.make('var/lib/omarchy/limine.enabled', '')
        self.menu = self.make('boot/efi/limine.conf', 'default_entry: Omarchy/linux-aurora\n')
        self.image = self.make('boot/efi/EFI/Linux/omarchy_linux-aurora.efi', uki('root=UUID=FRESH rw'))
        config = ('CONFIG_ARM64_16K_PAGES=y\nCONFIG_ARM64_USER4K_EXPERIMENTAL=y\nCONFIG_MM_SUBPAGE=y\n')
        self.kernel = self.make('usr/lib/modules/test/vmlinuz', b'ImageIKCFG_ST' + gzip.compress(config.encode()) + b'IKCFG_ED')

    def make(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def test_updates_real_source_preserves_machine_arguments_and_rebuilds_only_once(self):
        def rebuild(args, **kwargs):
            self.assertEqual(args, ['limine-mkinitcpio'])
            self.assertIn('rd.luks.name=FRESH-UUID=root rootflags=subvol=@ user4k=on', self.grub.read_text())
            self.limine.write_text('ESP_PATH="/boot/efi"\nKERNEL_CMDLINE[default]="root=UUID=FRESH rw user4k=on"\n')
            self.image.write_bytes(uki('root=UUID=FRESH rw user4k=on'))
        with patch.object(boot.subprocess, 'run', side_effect=rebuild) as command:
            self.assertTrue(boot.enable(self.root, 'test'))
            self.assertTrue(boot.enable(self.root, 'test'))
            command.assert_called_once()
        self.assertEqual(self.grub.read_text().count('user4k='), 1)
        self.assertIn("GRUB_CMDLINE_LINUX_DEFAULT='quiet splash' # owner comment", self.grub.read_text())
        self.assertEqual(self.menu.read_text(), 'default_entry: Omarchy/linux-aurora\n')
        self.assertEqual(len(list((self.root / 'var/lib/mac-steam-ultimate/boot-backups').iterdir())), 1)

    def test_missing_kernel_support_keeps_boot_files_unchanged(self):
        self.kernel.write_bytes(b'unsupported-kernel')
        before = self.grub.read_bytes()
        with patch.object(boot.subprocess, 'run') as command:
            self.assertFalse(boot.enable(self.root, 'test'))
            command.assert_not_called()
        self.assertEqual(self.grub.read_bytes(), before)

    def test_success_exit_with_stale_uki_restores_configs_and_images(self):
        files = [self.grub, self.limine, self.menu, self.image]
        before = {path: path.read_bytes() for path in files}
        extra = self.image.with_name('new-broken.efi')
        def rebuild(*args, **kwargs):
            self.menu.write_text('partially regenerated')
            self.limine.write_text('partially regenerated')
            self.image.write_bytes(uki('root=UUID=FRESH rw user4k=off'))
            extra.write_bytes(uki('root=UUID=FRESH rw user4k=off'))
        with patch.object(boot.subprocess, 'run', side_effect=rebuild):
            with self.assertRaisesRegex(ValueError, 'does not enable'):
                boot.enable(self.root, 'test')
        self.assertEqual({path: path.read_bytes() for path in files}, before)
        self.assertFalse(extra.exists())

    def test_failed_builder_restores_deleted_image(self):
        before = self.grub.read_bytes(), self.image.read_bytes()
        def rebuild(*args, **kwargs):
            self.image.unlink()
            raise subprocess.CalledProcessError(1, 'limine-mkinitcpio')
        with patch.object(boot.subprocess, 'run', side_effect=rebuild):
            with self.assertRaises(subprocess.CalledProcessError):
                boot.enable(self.root, 'test')
        self.assertEqual((self.grub.read_bytes(), self.image.read_bytes()), before)

    def test_missing_assignment_and_duplicate_off_switches(self):
        result = boot.boot_defaults('GRUB_CMDLINE_LINUX_DEFAULT="quiet user4k=off user4k=0"\n')
        self.assertEqual(result.count('user4k='), 1)
        self.assertIn('GRUB_CMDLINE_LINUX="user4k=on"', result)
        self.assertEqual(boot.boot_defaults(result), result)
        with self.assertRaisesRegex(ValueError, 'quoted'):
            boot.boot_defaults('GRUB_CMDLINE_LINUX=$(some-command)\n')


if __name__ == '__main__':
    unittest.main()
