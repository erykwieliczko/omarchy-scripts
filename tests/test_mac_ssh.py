"""Exercise SSH setup and rollback without changing this machine's SSH service."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'setup-mac-ssh.sh'


class SSHSetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.config = self.root / 'etc/ssh/sshd_config'
        self.config.parent.mkdir(parents=True)
        self.original = '# Owner config\nPort 2222\nPasswordAuthentication no\nPubkeyAuthentication yes\n'
        self.config.write_text(self.original)
        (self.root / 'run/lock').mkdir(parents=True)
        self.commands = self.root / 'commands'
        self.command('sshd', '''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if '-t' in args:
    sys.exit(1 if os.environ.get('FAIL_VALIDATION') else 0)
password='no' if os.environ.get('MATCH_REQUIRES_KEYS') else 'yes'
print('Port 2222')
print('PasswordAuthentication '+password)
print('AuthenticationMethods any')
print('PermitRootLogin prohibit-password')
print('PermitEmptyPasswords no')
''')
        self.command('ssh-keygen', '#!/usr/bin/env bash\nexit 0\n')
        self.command('systemctl', '''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$COMMANDS"
if [[ $1 == reload && -n ${FAIL_RELOAD:-} ]]; then exit 42; fi
exit 0
''')
        source = SCRIPT.read_text()
        for prefix in ('/etc/ssh/', '/var/lib/omarchy-ssh/', '/run/lock/'):
            source = source.replace(prefix, str(self.root) + prefix)
        source = source.replace('(( EUID != 0 ))', '(( 0 != 0 ))')
        self.script = self.root / 'setup.sh'
        self.script.write_text(source)
        self.environment = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', COMMANDS=str(self.commands))

    def command(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def launch(self, *arguments, **environment):
        return subprocess.run(['bash', str(self.script), '--user', 'player', *arguments],
                              env=dict(self.environment, **environment), capture_output=True, text=True)

    def test_password_policy_preserves_owner_config_and_existing_key_auth(self):
        for _ in range(2):
            result = self.launch()
            self.assertEqual(result.returncode, 0, result.stderr)
        text = self.config.read_text()
        self.assertTrue(text.startswith('# BEGIN OMARCHY PASSWORD SSH\nPasswordAuthentication yes'))
        self.assertIn('PermitRootLogin prohibit-password\n', text)
        self.assertIn('PermitEmptyPasswords no\n', text)
        self.assertIn('AuthenticationMethods any\n', text)
        self.assertIn(self.original, text)
        self.assertEqual(text.count('# BEGIN OMARCHY PASSWORD SSH'), 1)
        commands = self.commands.read_text()
        self.assertIn('reload sshd.service', commands)
        self.assertNotIn('restart', commands)

    def test_check_never_changes_configuration_or_service(self):
        result = self.launch('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse(self.commands.exists())

    def test_invalid_configuration_is_rejected_before_activation(self):
        result = self.launch(FAIL_VALIDATION='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertNotIn('reload', self.commands.read_text())
        self.assertEqual(list(self.config.parent.glob('.omarchy-password-*')), [])

    def test_account_match_rule_cannot_silently_keep_keys_required(self):
        result = self.launch(MATCH_REQUIRES_KEYS='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Match rule', result.stderr)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertNotIn('reload', self.commands.read_text())

    def test_reload_failure_restores_original_configuration_and_status(self):
        result = self.launch(FAIL_RELOAD='1')
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertIn('restored the previous configuration', result.stderr)


if __name__ == '__main__':
    unittest.main()
