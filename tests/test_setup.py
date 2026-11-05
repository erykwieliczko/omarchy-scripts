"""Verify selection, piped execution and failure boundaries without system changes."""
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPTS = {
    'P': 'install-mac-kde-ultimate-wip.sh',
    'G': 'install-mac-gnome-ultimate-wip.sh',
    'K': 'setup-mac-keyboard.sh',
    'S': 'install-mac-steam-ultimate-wip.sh',
    'H': 'setup-mac-ssh.sh',
}


class SetupSelection(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.downloads = self.root / 'downloads.jsonl'
        self.executions = self.root / 'executions.jsonl'
        self.scratch = self.root / 'scratch'
        self.scratch.mkdir()
        curl = self.root / 'curl'
        curl.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith('https://'))
name = url.rsplit('/', 1)[-1]
with open(os.environ['DOWNLOADS'], 'a') as out:
    out.write(json.dumps(url) + '\\n')
if name == os.environ.get('FAIL_DOWNLOAD'):
    sys.exit(22)
target = pathlib.Path(args[args.index('-o') + 1])
target.write_text(r"""#!/usr/bin/env bash
python3 - \"$@\" <<'CHILD'
import json, os, sys
with open(os.environ['EXECUTIONS'], 'a') as out:
    out.write(json.dumps({'name': NAME, 'args': sys.argv[1:]}) + '\\n')
sys.exit(19 if os.environ.get('FAIL_INSTALL') == NAME else 0)
CHILD
""".replace('NAME', repr(name)))
''')
        curl.chmod(0o755)
        self.environment = dict(os.environ, PATH=f'{self.root}:{os.environ["PATH"]}',
                                DOWNLOADS=str(self.downloads), EXECUTIONS=str(self.executions),
                                TMPDIR=str(self.scratch))

    def launch(self, *arguments, **environment):
        return subprocess.run(['bash', '-s', '--', *arguments], input=(ROOT / 'setup.sh').read_text(),
                              env=dict(self.environment, **environment), capture_output=True, text=True)

    def read_lines(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def reset_records(self):
        self.downloads.unlink(missing_ok=True)
        self.executions.unlink(missing_ok=True)

    def test_every_combination_fetches_and_runs_only_its_selected_components(self):
        for size in range(1, 6):
            for combination in itertools.combinations('PGKSH', size):
                if 'P' in combination and 'G' in combination:
                    continue
                options = ''.join(combination)
                with self.subTest(options=options):
                    self.reset_records()
                    result = self.launch('--options=' + options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = [SCRIPTS[letter] for letter in combination]
                    self.assertEqual([url.rsplit('/', 1)[-1] for url in self.read_lines(self.downloads)], expected)
                    self.assertEqual([item['name'] for item in self.read_lines(self.executions)], expected)
                    self.assertEqual(list(self.scratch.iterdir()), [])

    def test_normalizes_lowercase_duplicates_and_input_order(self):
        result = self.launch('-options=skppk')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([item['name'] for item in self.read_lines(self.executions)], [SCRIPTS[c] for c in 'PKS'])

    def test_invalid_or_empty_selection_never_downloads_or_executes(self):
        for arguments in ((), ('--options=',), ('--options=PX',), ('--options=PG',), ('--options=$(touch /bad)',), ('--unknown',)):
            with self.subTest(arguments=arguments):
                result = self.launch(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.downloads.exists())
                self.assertFalse(self.executions.exists())

    def test_pk_does_not_touch_steam_and_forwards_arguments_to_the_right_installers(self):
        result = self.launch('--options=PK', '--user', 'a literal account', '--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_lines(self.executions), [
            {'name': SCRIPTS['P'], 'args': ['--user', 'a literal account', '--check']},
            {'name': SCRIPTS['K'], 'args': ['--check']},
        ])
        self.assertIn('checks passed', result.stdout)
        self.assertNotIn('Reboot', result.stdout)

    def test_dry_run_prints_plan_without_downloading(self):
        result = self.launch('--options=PK', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(SCRIPTS['P'], result.stdout)
        self.assertIn(SCRIPTS['K'], result.stdout)
        self.assertNotIn(SCRIPTS['S'], result.stdout)
        self.assertFalse(self.downloads.exists())
        self.assertFalse(self.executions.exists())

    def test_right_option_preference_is_forwarded_only_to_keyboard(self):
        result = self.launch('--options=PKS', '--right-option=ctrl', '--user', 'player', '--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_lines(self.executions), [
            {'name': SCRIPTS['P'], 'args': ['--user', 'player', '--check']},
            {'name': SCRIPTS['K'], 'args': ['--right-option=ctrl', '--check']},
            {'name': SCRIPTS['S'], 'args': ['--user', 'player', '--check']},
        ])

    def test_right_option_requires_keyboard_and_a_supported_value(self):
        for args in (('--options=S', '--right-option=ctrl'),
                     ('--options=K', '--right-option=command'),
                     ('--options=K', '--right-option=')):
            with self.subTest(args=args):
                result = self.launch(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.downloads.exists())
                self.assertFalse(self.executions.exists())

    def test_download_failure_prevents_any_installation(self):
        result = self.launch('--options=PKS', FAIL_DOWNLOAD=SCRIPTS['K'])
        self.assertEqual(result.returncode, 22, result.stderr)
        self.assertFalse(self.executions.exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_child_failure_stops_following_components_and_keeps_exit_status(self):
        result = self.launch('--options=PKS', FAIL_INSTALL=SCRIPTS['K'])
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertEqual([item['name'] for item in self.read_lines(self.executions)], [SCRIPTS['P'], SCRIPTS['K']])
        self.assertIn('Stopped:', result.stderr)
        self.assertEqual(list(self.scratch.iterdir()), [])


class PublishedSite(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('build_site', ROOT / 'tools/build-site.py')
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def test_only_public_assets_are_published_and_installer_is_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            revision = 'a' * 40
            self.builder.build(ROOT, destination, revision)
            script = (destination / 'install.sh').read_text()
            self.assertIn(f'local revision={revision}\n', script)
            self.assertNotIn('local revision=main\n', script)
            self.assertTrue((destination / 'index.html').is_file())
            self.assertTrue((destination / '.nojekyll').is_file())
            self.assertFalse((destination / '.git').exists())
            subprocess.run(['bash', '-n', str(destination / 'install.sh')], check=True)

    def test_publication_requires_a_full_commit_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.builder.build(ROOT, Path(directory), 'main')


if __name__ == '__main__':
    unittest.main()
