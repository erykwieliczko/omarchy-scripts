import configparser
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

RUNTIME = Path(__file__).parents[1] / 'runtime'


def module(name):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class KDEIntegration(unittest.TestCase):
    def test_wallpaper_waits_for_the_first_desktop_layout(self):
        theme = module('theme')
        responses = [subprocess.CompletedProcess([], 0, 's "0"\n'),
                     subprocess.CompletedProcess([], 0, 's "1"\n')]
        with patch.object(theme.subprocess, 'run', side_effect=responses) as run:
            with patch.object(theme.time, 'sleep') as sleep:
                theme.wait_for_desktop()
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once()

    def test_palette_maps_omarchy_colors_into_kde(self):
        base = ''.join('[' + section + ']\n' for section in
                       ('Colors:Window', 'Colors:View', 'Colors:Selection', 'General', 'WM'))
        result = module('theme').make_scheme({'background': '#102030', 'accent': '#abcdef'}, base)
        self.assertEqual(result['Colors:Window']['BackgroundNormal'], '16,32,48')
        self.assertEqual(result['Colors:Selection']['BackgroundNormal'], '171,205,239')
        self.assertEqual(result['Colors:Selection']['ForegroundNormal'], '16,32,48')

    def test_invalid_palette_is_rejected(self):
        with self.assertRaises(ValueError):
            module('theme').make_scheme({'background': 'not a color'}, '[Colors:Window]\n')

    def test_user_settings_are_preserved_and_backed_up(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'kdeglobals'
            original = '[General]\nUserSetting=keep\nColorScheme=Original\n'
            path.write_text(original)
            module('setup-user').update_config(path, {'General': {'ColorScheme': 'Omarchy'}})
            config = configparser.ConfigParser()
            config.read(path)
            self.assertEqual(config['General']['UserSetting'], 'keep')
            self.assertEqual(path.with_name('kdeglobals.pre-omarchy-kde').read_text(), original)

    def test_kde_launcher_preserves_literal_arguments(self):
        environment = dict(os.environ, XDG_CURRENT_DESKTOP='KDE')
        result = subprocess.run(['bash', str(RUNTIME / 'uwsm-app'), '--',
                                 'printf', '%s\n', 'hello world', 'literal$', '--flag'],
                                env=environment, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'hello world\nliteral$\n--flag\n')

    def test_switch_stops_installed_managers_when_another_is_missing(self):
        for runtime in (RUNTIME, RUNTIME.parents[1] / 'gnome/runtime'):
            with self.subTest(desktop=runtime.parent.name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                scripts = {
                    'id': 'echo 1000\n',
                    'pgrep': 'exit 1\n',
                    'loginctl': 'exit 0\n',
                    'systemctl': '''if [ "$1" = stop ]; then
    shift
    for unit in "$@"; do
        [ "$unit" != sddm.service ] || exit 5
    done
    printf '%s\\n' "$@" >> "$SWITCH_STOPS"
fi
''',
                }
                for name, body in scripts.items():
                    path = root / name
                    path.write_text('#!/bin/sh\n' + body)
                    path.chmod(0o755)
                record = root / 'stopped'
                subprocess.run(['bash', str(runtime / 'switch-desktop'), 'player'],
                               env=dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                                        SWITCH_STOPS=str(record)), check=True)
                stopped = record.read_text().splitlines()
                self.assertIn('plasmalogin.service', stopped)
                self.assertIn('greetd.service', stopped)
                if runtime == RUNTIME:
                    self.assertIn('gdm.service', stopped)

    def test_retiring_focus_workaround_preserves_other_window_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'kwinrulesrc'
            original = ('[General]\nOrder=user,omarchy-aoe2-focus,other\n'
                        '[user]\nacceptfocus=false\nwmclass=my-app\n'
                        '[omarchy-aoe2-focus]\nacceptfocus=true\n'
                        '[other]\nopacityactive=90\n')
            path.write_text(original)
            module('setup-user').retire_focus_rule(path)
            config = configparser.ConfigParser()
            config.read(path)
            self.assertEqual(config['General']['order'], 'user,other')
            self.assertEqual(config['user']['acceptfocus'], 'false')
            self.assertEqual(config['other']['opacityactive'], '90')
            self.assertNotIn('omarchy-aoe2-focus', config)
            self.assertEqual(path.with_name('kwinrulesrc.pre-wine-focus-repair').read_text(), original)


if __name__ == '__main__':
    unittest.main()
