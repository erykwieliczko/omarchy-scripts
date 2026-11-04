"""Check login preferences and GNOME integration without touching the host."""
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


class GNOMEIntegration(unittest.TestCase):
    def test_password_login_preserves_other_gdm_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'etc/gdm/custom.conf'
            path.parent.mkdir(parents=True)
            path.write_text('[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=someone\n'
                            'TimedLoginEnable=true\n[debug]\nEnable=true\n')
            module('configure').configure(root)
            config = configparser.ConfigParser()
            config.read(path)
            self.assertEqual(config['daemon']['AutomaticLoginEnable'], 'false')
            self.assertEqual(config['daemon']['TimedLoginEnable'], 'false')
            self.assertEqual(config['daemon']['AutomaticLogin'], 'someone')
            self.assertEqual(config['debug']['Enable'], 'true')

    def test_existing_account_session_is_updated_through_supported_api(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if 'FindUserByName' in command:
                return subprocess.CompletedProcess(command, 0, 'o "/org/freedesktop/Accounts/User1000"\n')
            if 'introspect' in command:
                return subprocess.CompletedProcess(command, 0, '.SetSession method s -\n.SetXSession method s -\n.SetSessionType method s -\n')
            return subprocess.CompletedProcess(command, 0, '')
        login = module('configure')
        with patch.object(login.subprocess, 'run', side_effect=run):
            login.set_user_session('player')
        self.assertEqual([call[-3:] for call in calls[2:]], [
            ['SetSession', 's', 'omarchy-gnome'],
            ['SetXSession', 's', 'omarchy-gnome'],
            ['SetSessionType', 's', 'wayland'],
        ])

    def test_user_setup_keeps_other_desktops_and_user_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / '.config'
            config.mkdir()
            original = config / 'gtk-settings-preserved'
            original.write_text('owner settings')
            setup = module('setup-user')
            setup.configure(home)
            setup.configure(home)
            self.assertEqual(original.read_text(), 'owner settings')
            dropin = config / 'systemd/user/omarchy-fcitx5.service.d/90-omarchy-gnome.conf'
            self.assertIn('ConditionEnvironment=!XDG_CURRENT_DESKTOP=GNOME', dropin.read_text())
            self.assertFalse((config / 'systemd/user/omarchy-fcitx5.service').is_symlink())
            generator = config / 'systemd/user-environment-generators/90-omarchy-gnome'
            self.assertEqual(os.readlink(generator), '/usr/local/lib/omarchy-gnome/environment-generator')

    def test_session_removes_inherited_hyprland_and_plasma_settings(self):
        environment = dict(os.environ, PATH='/usr/local/lib/omarchy-kde/bin:/usr/bin',
                           GTK_THEME='wrong', GDK_SCALE='2', QT_QPA_PLATFORMTHEME='kde',
                           HYPRLAND_INSTANCE_SIGNATURE='old', KDE_FULL_SESSION='true',
                           QT_IM_MODULE='fcitx', INPUT_METHOD='fcitx')
        result = subprocess.run(['bash', '-c', 'source "$1"; env', 'fixture',
                                 str(RUNTIME / 'session-env.sh')],
                                env=environment, capture_output=True, text=True, check=True)
        actual = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        self.assertEqual(actual['XDG_CURRENT_DESKTOP'], 'GNOME')
        self.assertTrue(actual['PATH'].startswith('/usr/local/lib/omarchy-gnome/bin:'))
        self.assertNotIn('/usr/local/lib/omarchy-kde/bin', actual['PATH'])
        for key in ('GTK_THEME', 'GDK_SCALE', 'QT_QPA_PLATFORMTHEME', 'QT_IM_MODULE',
                    'INPUT_METHOD', 'HYPRLAND_INSTANCE_SIGNATURE', 'KDE_FULL_SESSION'):
            self.assertNotIn(key, actual)

    def test_environment_generator_only_changes_gnome(self):
        for desktop in ('GNOME', 'Hyprland', 'KDE'):
            result = subprocess.run(['sh', str(RUNTIME / 'environment-generator')],
                                    env=dict(os.environ, XDG_CURRENT_DESKTOP=desktop),
                                    capture_output=True, text=True, check=True)
            self.assertEqual(bool(result.stdout), desktop == 'GNOME')

    def test_native_app_launcher_preserves_literal_arguments(self):
        result = subprocess.run(['bash', str(RUNTIME / 'uwsm-app'), '--', 'printf',
                                 '%s\n', 'hello world', 'literal$', '--flag'],
                                env=dict(os.environ, XDG_CURRENT_DESKTOP='GNOME'),
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'hello world\nliteral$\n--flag\n')


if __name__ == '__main__':
    unittest.main()
