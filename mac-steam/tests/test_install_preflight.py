"""Run real installer preflight against dependency and hardware fixtures."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


INSTALLER = Path(__file__).parents[1] / 'install.sh'


class InstallPreflight(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.home = self.root / 'player'
        self.home.mkdir()
        self.compatible = self.root / 'compatible'
        self.arch_release = self.root / 'arch-release'
        self.arch_release.touch()
        source = INSTALLER.read_text().replace('/etc/arch-release', str(self.arch_release))
        source = source.replace('/proc/device-tree/compatible', str(self.compatible))
        self.script = self.root / 'install.sh'
        self.script.write_text(source)
        self.command('uname', 'echo "${TEST_ARCH:-aarch64}"')
        self.command('pacman-conf', 'printf "%s\\n" "${TEST_STEAM_REPO:-omarchy}" "${TEST_ASAHI_REPO:-asahi-alarm}"')
        self.command('id', 'echo 1000')
        self.command('getent', 'printf "%s\\n" ' + shlex.quote(f'player:x:1000:1000::{self.home}:/bin/bash'))

    def command(self, name, body):
        path = self.bin / name
        path.write_text('#!/usr/bin/env bash\nset -eu\n' + body + '\n')
        path.chmod(0o755)

    def run_preflight(self, **environment):
        return subprocess.run(['bash', str(self.script), '--user', 'player', '--check'],
                              env=dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                                       **environment), capture_output=True, text=True)

    def test_chip_and_board_identity_do_not_gate_installation(self):
        for compatible in (b'apple,t8112\0apple,arm-platform\0',
                           b'apple,j516s\0apple,t6030\0apple,arm-platform\0',
                           b'apple,future-chip\0'):
            with self.subTest(compatible=compatible):
                self.compatible.write_bytes(compatible)
                result = self.run_preflight()
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_machine_identity_does_not_gate_installation(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_binary_architecture_is_rejected(self):
        result = self.run_preflight(TEST_ARCH='x86_64')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ARM64', result.stderr)

    def test_missing_package_repository_is_rejected(self):
        result = self.run_preflight(TEST_STEAM_REPO='unrelated')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Required pacman repository', result.stderr)

    def test_dependencies_can_come_from_differently_named_repositories(self):
        result = self.run_preflight(TEST_ASAHI_REPO='other-graphics-repo')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
