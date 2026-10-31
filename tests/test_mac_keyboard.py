"""Exercise installation and recovery in a temporary filesystem, without sudo."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / 'setup-mac-keyboard.sh'
ORIGINAL = 'options hid_apple fnmode=1 swap_opt_cmd=0 swap_fn_leftctrl=0\n'
DESIRED = 'options hid_apple fnmode=2 swap_opt_cmd=1 swap_fn_leftctrl=1'


class MacKeyboard(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mac-keyboard-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.environment = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}')
        self.config = self.root / 'etc/modprobe.d/apple-keyboard.conf'
        self.parameters = self.root / 'sys/module/hid_apple/parameters'
        self.backups = self.root / 'var/lib/omarchy-mac-keyboard/backups'
        self.write('etc/arch-release', '')
        self.write('proc/device-tree/compatible', 'apple,j514\0apple,arm-platform\0')
        self.write('usr/bin/omarchy', '', executable=True)
        self.write('etc/modprobe.d/apple-keyboard.conf', ORIGINAL)
        for name, value in (('fnmode', 1), ('swap_opt_cmd', 0), ('swap_fn_leftctrl', 0)):
            self.write(f'sys/module/hid_apple/parameters/{name}', f'{value}\n')
        self.images = [self.write(f'boot/initramfs-{name}.img', f'original-{name}')
                       for name in ('linux-aurora', 'linux-aurora-dsc')]
        (self.root / 'run/lock').mkdir(parents=True)
        self.command('uname', 'echo "${MOCK_ARCH:-aarch64}"')
        self.command('modprobe', f'cat {shlex.quote(str(self.config))}\n'
                     'if [[ -n ${MOCK_CONFLICT:-} ]]; then echo "options hid_apple fnmode=1"; fi')
        self.command('mkinitcpio', '\n'.join(
            f'printf rebuilt > {shlex.quote(str(image))}' for image in self.images
        ) + '\nexit "${MOCK_BUILD_STATUS:-0}"')

        # Redirect every system path into the fixture, and bypass only the root
        # check. All real file writes, backups, traps, and rollback logic execute.
        source = SCRIPT.read_text()
        for prefix in ('/etc/', '/proc/device-tree/', '/usr/bin/omarchy', '/sys/',
                       '/var/lib/', '/run/lock/', '/boot/'):
            source = source.replace(prefix, str(self.root) + prefix)
        source = source.replace('(( EUID != 0 ))', '(( 0 != 0 ))')
        self.script = self.write('setup.sh', source)

    def write(self, relative, content, executable=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if executable:
            path.chmod(0o755)
        return path

    def command(self, name, body):
        self.write(f'bin/{name}', '#!/usr/bin/env bash\nset -eu\n' + body + '\n', True)

    def run_script(self, *arguments, **environment):
        return subprocess.run(['bash', str(self.script), *arguments],
                              env=dict(self.environment, **environment),
                              text=True, capture_output=True)

    def assert_original(self):
        self.assertEqual(self.config.read_text(), ORIGINAL)
        self.assertEqual((self.parameters / 'fnmode').read_text(), '1\n')
        self.assertEqual((self.parameters / 'swap_opt_cmd').read_text(), '0\n')
        self.assertEqual((self.parameters / 'swap_fn_leftctrl').read_text(), '0\n')
        for image in self.images:
            self.assertEqual(image.read_text(), f'original-{image.name[10:-4]}')

    def test_check_is_read_only(self):
        result = self.run_script('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_original()
        self.assertFalse(self.backups.exists())

    def test_unsupported_platform_is_rejected_before_changes(self):
        result = self.run_script(MOCK_ARCH='x86_64')
        self.assertNotEqual(result.returncode, 0)
        self.assert_original()
        self.assertFalse(self.backups.exists())

    def test_install_and_repeat_preserve_backups(self):
        for _ in range(2):
            result = self.run_script()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('No reboot needed', result.stdout)
            self.assertIn(DESIRED, self.config.read_text())
            self.assertEqual((self.parameters / 'fnmode').read_text(), '2\n')
            self.assertEqual((self.parameters / 'swap_opt_cmd').read_text(), '1\n')
            self.assertEqual((self.parameters / 'swap_fn_leftctrl').read_text(), '1\n')
        backups = sorted(self.backups.iterdir())
        self.assertEqual(len(backups), 2)
        self.assertTrue(any((backup / 'apple-keyboard.conf').read_text() == ORIGINAL
                            for backup in backups))

    def test_failed_rebuild_restores_config_runtime_and_both_images(self):
        result = self.run_script(MOCK_BUILD_STATUS='42')
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertIn('Previous settings restored', result.stderr)
        self.assert_original()

    def test_conflicting_config_is_rejected_and_restored(self):
        result = self.run_script(MOCK_CONFLICT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('override this configuration', result.stderr)
        self.assert_original()

    def test_failed_first_install_removes_new_config(self):
        self.config.unlink()
        result = self.run_script(MOCK_BUILD_STATUS='42')
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertFalse(self.config.exists())

    def test_piped_installer_passes_complete_function_through_sudo(self):
        source = self.script.read_text().replace('(( 0 != 0 ))', '(( 1 != 0 ))')
        self.write('bin/sudo', '''#!/usr/bin/env python3
import os
import sys
assert sys.argv[1:4] == ['--', 'bash', '-c'], sys.argv
body = sys.argv[4].replace('(( 1 != 0 ))', '(( 0 != 0 ))')
os.execvp('bash', ['bash', '-c', body, *sys.argv[5:]])
''', executable=True)
        result = subprocess.run(['bash', '-s', '--'], input=source,
                                env=self.environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Applying keyboard settings (sudo)', result.stdout)
        self.assertIn('No reboot needed', result.stdout)
        self.assertIn(DESIRED, self.config.read_text())


if __name__ == '__main__':
    unittest.main()
