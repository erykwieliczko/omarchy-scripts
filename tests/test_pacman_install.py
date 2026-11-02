"""Check package-only fallback policy, transaction status and temporary cleanup."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).parents[1] / 'common/pacman-install.sh'


class PackageTransaction(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'original.conf'
        self.config.write_text('''[options]
Architecture = aarch64
SigLevel = PackageRequired DatabaseOptional
[omarchy]
Server = https://pkgs.omarchy.org/edge/aarch64
[asahi-alarm]
Server = https://github.com/asahi-alarm/asahi-alarm/releases/download/aarch64
[extra]
Server = https://arm-mirror.omarchy.org/aarch64/extra
[core]
Server = https://arm-rc-mirror.omarchy.org/aarch64/core
[alarm]
Server = https://arm-stable-mirror.omarchy.org/aarch64/alarm
[custom]
Server = https://example.org/custom
''')
        self.result = self.root / 'result.json'
        self.command('pacman-conf', '#!/usr/bin/env bash\ncat "$ORIGINAL_CONFIG"\n')
        self.command('pacman', '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
config=Path(sys.argv[2])
Path(os.environ['RESULT']).write_text(json.dumps({'arguments':sys.argv[1:], 'config':config.read_text(), 'temporary':str(config.parent)}))
sys.exit(int(os.environ.get('EXIT_STATUS','0')))
''')
        self.environment = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                                ORIGINAL_CONFIG=str(self.config), RESULT=str(self.result))

    def command(self, name, text):
        path = self.root / name
        path.write_text(text)
        path.chmod(0o755)

    def launch(self):
        return subprocess.run(['bash', '-c', 'source "$1"; mac_install_packages "${@:2}"',
                               'fixture', str(HELPER), 'plasma-meta', 'omarchy/steam'],
                              env=self.environment, capture_output=True, text=True)

    def test_preserves_repository_sources_signatures_and_package_only_transaction(self):
        before = self.config.read_bytes()
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.result.read_text())
        self.assertEqual(data['arguments'][2:], ['-S', '--needed', '--noconfirm', 'plasma-meta', 'omarchy/steam'])
        self.assertEqual(data['config'].count('CacheServer = '), 3)
        self.assertIn('SigLevel = PackageRequired DatabaseOptional', data['config'])
        self.assertIn('Server = https://arm-mirror.omarchy.org/aarch64/extra', data['config'])
        for repository in ('omarchy', 'asahi-alarm', 'custom'):
            section = data['config'].split('[' + repository + ']\n')[1].split('[')[0]
            self.assertNotIn('CacheServer', section)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse(Path(data['temporary']).exists())

    def test_failed_transaction_returns_failure_and_removes_temporary_config(self):
        self.environment['EXIT_STATUS'] = '42'
        self.assertEqual(self.launch().returncode, 42)
        data = json.loads(self.result.read_text())
        self.assertFalse(Path(data['temporary']).exists())

    def test_no_fallback_for_a_different_distribution_mirror(self):
        self.config.write_text(self.config.read_text().replace('arm-mirror.omarchy.org', 'mirror.example.org')
                               .replace('arm-rc-mirror.omarchy.org', 'mirror.example.org')
                               .replace('arm-stable-mirror.omarchy.org', 'mirror.example.org'))
        self.assertEqual(self.launch().returncode, 0)
        self.assertNotIn('CacheServer', json.loads(self.result.read_text())['config'])


if __name__ == '__main__':
    unittest.main()
