"""Exercise host GameMode ownership, child exit and signal cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

WRAPPER = Path(__file__).parents[1] / 'runtime/with-gamemode.py'
RUNNER = '''import os, runpy, sys
from pathlib import Path
module = runpy.run_path(sys.argv[1], run_name='fixture')
class Function:
    def __init__(self, name):
        self.name = name
    def __call__(self):
        with open(os.environ['LEASE_LOG'], 'a') as log:
            log.write(self.name + '\\n')
        if self.name == 'error':
            return b'test refusal'
        return -1 if self.name == 'start' and os.environ.get('REFUSE') else 0
class Client:
    real_gamemode_request_start = Function('start')
    real_gamemode_request_end = Function('end')
    real_gamemode_error_string = Function('error')
def load(name):
    if os.environ.get('MISSING_LIBRARY'):
        raise OSError('library missing')
    return Client()
module['ctypes'].CDLL = load
sys.exit(module['main'](sys.argv[2:]))
'''


class GameModeLifetime(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='steam-gamemode-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / 'lease.log'
        self.environment = dict(os.environ, LEASE_LOG=str(self.log))

    def launch(self, command):
        process = subprocess.Popen([sys.executable, '-c', RUNNER, str(WRAPPER), *command],
                                   env=self.environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()
        self.addCleanup(cleanup)
        return process

    def test_waits_for_child_preserves_arguments_environment_and_exit_status(self):
        result = self.root / 'child.json'
        code = '''import json, os, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'args': sys.argv[2:], 'preload': os.getenv('LD_PRELOAD')}))
sys.exit(7)
'''
        process = self.launch([sys.executable, '-c', code, str(result), 'a space', 'steam://rungameid/813780'])
        self.assertEqual(process.wait(timeout=5), 7, process.stderr.read())
        self.assertEqual(self.log.read_text().splitlines(), ['start', 'end'])
        self.assertEqual(json.loads(result.read_text()),
                         {'args': ['a space', 'steam://rungameid/813780'],
                          'preload': os.environ.get('LD_PRELOAD')})

    def test_termination_reaches_child_before_request_is_released(self):
        ready = self.root / 'ready'
        stopped = self.root / 'stopped'
        code = '''import signal, sys, time
from pathlib import Path
def stop(signum, frame):
    Path(sys.argv[2]).write_text('stopped')
    sys.exit(128 + signum)
signal.signal(signal.SIGTERM, stop)
Path(sys.argv[1]).touch()
while True:
    time.sleep(1)
'''
        process = self.launch([sys.executable, '-c', code, str(ready), str(stopped)])
        deadline = time.monotonic() + 5
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), 'Child never started')
        self.assertEqual(self.log.read_text().splitlines(), ['start'])
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 143, process.stderr.read())
        self.assertTrue(stopped.exists())
        self.assertEqual(self.log.read_text().splitlines(), ['start', 'end'])

    def test_failed_launch_releases_request(self):
        process = self.launch([str(self.root / 'no-such-command')])
        self.assertEqual(process.wait(timeout=5), 127)
        self.assertEqual(self.log.read_text().splitlines(), ['start', 'end'])

    def test_child_crash_releases_request_and_preserves_signal_status(self):
        process = self.launch([sys.executable, '-c',
                               'import os, signal; os.kill(os.getpid(), signal.SIGKILL)'])
        self.assertEqual(process.wait(timeout=5), 137)
        self.assertEqual(self.log.read_text().splitlines(), ['start', 'end'])

    def test_missing_library_still_runs_child(self):
        self.environment['MISSING_LIBRARY'] = '1'
        process = self.launch([sys.executable, '-c', 'print("started")'])
        output, error = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        self.assertIn(b'started', output)
        self.assertIn(b'continuing normally', error)
        self.assertFalse(self.log.exists())

    def test_refused_request_still_runs_child_without_releasing_unowned_request(self):
        self.environment['REFUSE'] = '1'
        process = self.launch([sys.executable, '-c', 'pass'])
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertIn(b'test refusal', process.stderr.read())
        self.assertEqual(self.log.read_text().splitlines(), ['start', 'error'])

    def test_empty_command_is_rejected_without_request(self):
        process = self.launch([])
        self.assertEqual(process.wait(timeout=5), 2)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
