"""Exercise readiness, socket lifetime and cleanup with real process pipes."""
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import unittest

WRAPPER = Path(__file__).parents[1] / 'runtime/fex-server-manager'
RUNNER = '''import runpy, sys
from pathlib import Path
module = runpy.run_path(sys.argv[1], run_name='fixture')
module['main'].__globals__['MANAGER'] = Path(sys.argv[2])
sys.argv = [sys.argv[1]]
sys.exit(module['main']())
'''


class ServerLifetime(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='fex-lease-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.library = self.root / 'Steam library'
        self.marker = self.root / 'native-exited'
        self.native = self.root / 'native-manager'
        self.native.write_text(f'''#!{sys.executable}
import os, sys
from pathlib import Path
try:
    os.write(1, os.environ.get('FIXTURE_READY', 'READY=1\\n').encode())
    os.close(1)
    sys.stdout = open(os.devnull, 'w')
    while sys.stdin.buffer.read(4096):
        pass
finally:
    Path({str(self.marker)!r}).write_text('closed')
''')
        self.native.chmod(0o755)
        self.environment = dict(os.environ, STEAM_COMPAT_DATA_PATH=str(self.library))
        address = self.library / f'fex-emu/Server/{os.getuid()}.FEXServer.Socket'
        address.parent.mkdir(parents=True)
        self.server = socket.socket(socket.AF_UNIX)
        self.addCleanup(self.server.close)
        self.server.bind(str(address))
        self.server.listen()
        self.server.settimeout(3)

    def launch(self):
        process = subprocess.Popen([sys.executable, '-c', RUNNER, str(WRAPPER), str(self.native)],
                                   env=self.environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.addCleanup(cleanup)
        return process

    def ready(self, process):
        self.assertTrue(select.select([process.stdout], [], [], 3)[0])
        self.assertEqual(process.stdout.readline(), b'READY=1\n')
        # pressure-vessel needs EOF as well as the readiness line.
        self.assertTrue(select.select([process.stdout], [], [], 3)[0], 'Readiness pipe held open')
        self.assertEqual(process.stdout.read(), b'')
        connection, _ = self.server.accept()
        self.addCleanup(connection.close)
        connection.settimeout(0.05)
        with self.assertRaises(socket.timeout):
            connection.recv(1)
        return connection

    def test_existing_server_is_held_until_input_eof_and_native_child_exits(self):
        process = self.launch()
        connection = self.ready(process)
        self.assertFalse(self.marker.exists())
        process.stdin.close()
        self.assertEqual(process.wait(timeout=3), 0, process.stderr.read())
        connection.settimeout(3)
        self.assertEqual(connection.recv(1), b'')
        self.assertEqual(self.marker.read_text(), 'closed')

    def test_termination_releases_socket_and_native_child(self):
        process = self.launch()
        connection = self.ready(process)
        process.terminate()
        self.assertEqual(process.wait(timeout=3), 143, process.stderr.read())
        connection.settimeout(3)
        self.assertEqual(connection.recv(1), b'')
        self.assertTrue(self.marker.exists())

    def test_unready_native_manager_never_signals_success(self):
        self.environment['FIXTURE_READY'] = 'FAILED\n'
        process = self.launch()
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(process.stdout.read(), b'')
        self.assertTrue(self.marker.exists())

    def test_missing_server_never_signals_success(self):
        self.server.close()
        process = self.launch()
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(process.stdout.read(), b'')
        self.assertTrue(self.marker.exists())

    def test_long_library_path_uses_steam_temporary_socket(self):
        self.server.close()
        self.server = socket.socket(socket.AF_UNIX)
        self.addCleanup(self.server.close)
        self.environment.update(STEAM_COMPAT_DATA_PATH=str(self.root / ('x' * 120)),
                                XDG_RUNTIME_DIR=str(self.root), SteamAppId='813780')
        self.server.bind(str(self.root / '813780.FEXServer.Socket'))
        self.server.listen()
        self.server.settimeout(3)
        process = self.launch()
        connection = self.ready(process)
        process.stdin.close()
        self.assertEqual(process.wait(timeout=3), 0, process.stderr.read())
        connection.settimeout(3)
        self.assertEqual(connection.recv(1), b'')


if __name__ == '__main__':
    unittest.main()
