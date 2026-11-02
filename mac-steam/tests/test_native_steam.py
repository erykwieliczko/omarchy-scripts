"""Exercise native launcher privilege separation and existing-session identity."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).parents[1] / 'runtime/native-steam'
loader = importlib.machinery.SourceFileLoader('native_steam', str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
native = importlib.util.module_from_spec(spec)
loader.exec_module(native)


class NativeLaunch(unittest.TestCase):
    def setUp(self):
        self.account = pwd.struct_passwd(('player', 'x', 1000, 1000, '', '/home/player', '/bin/bash'))
        self.prefix = Path('/opt/mac-steam-ultimate/releases/test')

    def test_only_desktop_variables_enter_unprivileged_child_environment(self):
        environment = ('DISPLAY=:1\nXDG_RUNTIME_DIR=/wrong\nHOME=/root\nPATH=/bad\n'
                       'LD_PRELOAD=/bad.so\nPYTHONPATH=/bad\nLANG=pl_PL.UTF-8\n'
                       'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus\n')
        result = subprocess.CompletedProcess([], 0, environment, '')
        with patch.object(native, 'run', return_value=result):
            command = native.user_command(self.account, self.prefix,
                                           ['/usr/bin/steam', 'steam://rungameid/813780', 'a space'])
        self.assertEqual(command[:7], ['/usr/bin/runuser', '-u', 'player', '--', '/usr/bin/env', '-i',
                                       'HOME=/home/player'])
        self.assertIn('XDG_RUNTIME_DIR=/run/user/1000', command)
        self.assertIn('DISPLAY=:1', command)
        self.assertNotIn('LD_PRELOAD=/bad.so', command)
        self.assertNotIn('PYTHONPATH=/bad', command)
        self.assertEqual(command[-4:], ['4k', '/usr/bin/steam', 'steam://rungameid/813780', 'a space'])

    def test_missing_desktop_never_starts_steam(self):
        with patch.object(native, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            with self.assertRaisesRegex(ValueError, 'no XWayland'):
                native.desktop_environment(self.account, self.prefix)

    def test_existing_session_checks_account_and_process_identity_before_nsenter(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'session.json'
            data = {'uid': 1000, 'pid': 123, 'identity': ['42', 'mnt:[test]'],
                    'prefix': str(self.prefix)}
            state.write_text(json.dumps(data))
            with patch.object(native, 'STATE', state), \
                    patch.object(native, 'identity', return_value=('43', 'mnt:[test]')), \
                    patch.object(native, 'wait_for') as launch:
                with self.assertRaisesRegex(ValueError, 'has exited'):
                    native.send_existing(self.account, [])
                launch.assert_not_called()
            data['uid'] = 2000
            state.write_text(json.dumps(data))
            with patch.object(native, 'STATE', state), patch.object(native, 'wait_for') as launch:
                with self.assertRaisesRegex(ValueError, 'Another account'):
                    native.send_existing(self.account, [])
                launch.assert_not_called()

    def test_process_identity_handles_spaces_and_parentheses_in_comm(self):
        with patch.object(Path, 'read_text', return_value='123 (a tricky) process) S ' + ' '.join(str(n) for n in range(1, 25))), \
                patch.object(native.os, 'readlink', return_value='mnt:[123]'):
            self.assertEqual(native.identity(123), ('19', 'mnt:[123]'))

    def test_ordinary_invocation_and_system_accounts_are_rejected(self):
        with patch.object(native.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'through steam-mac-ultimate'):
                native.main([])
        with patch.object(native.os, 'geteuid', return_value=0), \
                patch.dict(os.environ, {'PKEXEC_UID': '0'}):
            with self.assertRaisesRegex(ValueError, 'regular desktop account'):
                native.main([])

    def test_internal_mount_worker_cannot_be_requested_directly(self):
        with patch.object(native.os, 'geteuid', return_value=0), \
                patch.dict(os.environ, {'PKEXEC_UID': '1000'}, clear=True), \
                patch.object(native.pwd, 'getpwuid', return_value=self.account), \
                patch.object(native, 'inside') as worker:
            with self.assertRaisesRegex(ValueError, 'requires its supervisor'):
                native.main(['--inside'])
            worker.assert_not_called()


if __name__ == '__main__':
    unittest.main()
