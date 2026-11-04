"""Check login preferences and GNOME integration without touching the host."""
import configparser
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


RUNTIME = Path(__file__).parents[1] / 'runtime'


def module(name):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class GNOMEIntegration(unittest.TestCase):
    def test_flatpak_driver_setup_leaves_non_aurora_graphics_untouched(self):
        setup = module('setup-flatpak-gl')
        with patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            with patch.object(setup.pwd, 'getpwnam') as account:
                setup.install('player')
        self.assertEqual(run.call_count, 1)
        account.assert_not_called()

    def test_flatpak_loader_defaults_keep_existing_driver_choices(self):
        setup = module('setup-flatpak-gl')
        choices = setup.missing_loader_defaults(
            '[Context]\nshared=network;\n[Environment]\n'
            'VK_DRIVER_FILES=/owner/driver.json\nOTHER=literal%value\n')
        self.assertNotIn('VK_DRIVER_FILES', choices)
        self.assertIn('__EGL_VENDOR_LIBRARY_FILENAMES', choices)
        self.assertNotIn('OTHER', choices)

    def test_corrupt_graphics_archive_is_rejected_before_extracting_or_registering(self):
        setup = module('setup-flatpak-gl')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if command[0] == 'curl':
                    Path(command[command.index('-o') + 1]).write_bytes(b'corrupt download')
                return subprocess.CompletedProcess(command, 0)
            with patch.object(setup, 'Path', side_effect=lambda value: root / value.lstrip('/')):
                with patch.object(setup.subprocess, 'run', side_effect=run):
                    with patch.object(setup.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)):
                        with self.assertRaisesRegex(RuntimeError, 'checksum failed'):
                            setup.install('player')
            self.assertEqual([call[0] for call in calls], ['pacman', 'curl'])
            self.assertFalse((root / 'usr/local/share/omarchy-gnome/flatpak-gl').exists())
            self.assertFalse(list(root.rglob('*.partial')))

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

    def test_fcitx_autostart_is_only_excluded_from_gnome(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / '.config/autostart/org.fcitx.Fcitx5.desktop'
            path.parent.mkdir(parents=True)
            original = '[Desktop Entry]\nType=Application\nExec=fcitx5\nNotShowIn=Other;\n'
            path.write_text(original)
            setup = module('setup-user')
            setup.configure(home)
            setup.configure(home)
            config = configparser.ConfigParser()
            config.read(path)
            self.assertEqual(config['Desktop Entry']['NotShowIn'], 'Other;GNOME;')
            self.assertEqual(config['Desktop Entry']['Exec'], 'fcitx5')
            self.assertNotIn('Hidden', config['Desktop Entry'])
            self.assertEqual(path.with_suffix('.desktop.pre-omarchy-gnome').read_text(), original)

    def test_partial_autostart_mask_gets_required_desktop_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / '.config/autostart/org.fcitx.Fcitx5.desktop'
            path.parent.mkdir(parents=True)
            original = '[Desktop Entry]\nHidden=true\nNotShowIn=GNOME;\n'
            path.write_text(original)
            template = home / 'system-fcitx.desktop'
            template.write_text('[Desktop Entry]\nType=Application\nName=Fcitx 5\nExec=/usr/bin/fcitx5\n')
            setup = module('setup-user')
            setup.configure(home, template)
            setup.configure(home, template)
            config = configparser.ConfigParser()
            config.read(path)
            self.assertEqual(config['Desktop Entry']['Type'], 'Application')
            self.assertEqual(config['Desktop Entry']['Name'], 'Fcitx 5')
            self.assertEqual(config['Desktop Entry']['Exec'], '/usr/bin/fcitx5')
            self.assertEqual(config['Desktop Entry']['Hidden'], 'true')
            self.assertEqual(config['Desktop Entry']['NotShowIn'], 'GNOME;')
            self.assertEqual(path.with_suffix('.desktop.pre-omarchy-gnome').read_text(), original)

    def test_desktop_profile_preserves_later_choices_power_favorites_and_custom_shortcuts(self):
        class Value:
            def __init__(self, value): self.value = value
            def print_(self, unused): return repr(self.value)
            def unpack(self): return self.value
            def get_type_string(self): return 'fixture'
        class Settings:
            def __init__(self, schema): self.values = store.setdefault(schema, {})
            def get_user_value(self, key): return self.values.get(key)
            def get_value(self, key): return self.values.get(key, Value([]))
            def set_value(self, key, value): self.values[key] = value; return True
            def reset(self, key): self.values.pop(key, None)
        media = 'org.gnome.settings-daemon.plugins.media-keys'
        power = 'org.gnome.settings-daemon.plugins.power'
        interface = 'org.gnome.desktop.interface'
        store = {media: {'custom-keybindings': Value(['/owner-shortcut/'])},
                 'org.gnome.shell': {'favorite-apps': Value(['owner.desktop'])},
                 power: {'sleep-inactive-ac-type': Value('nothing')},
                 interface: {'icon-theme': Value('OwnerIcons')}}
        defaults = module('desktop-defaults')
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            defaults.apply_once(state, Settings, lambda kind, value: Value(value), 'browser.desktop')
            self.assertEqual(store['org.gnome.shell']['favorite-apps'].unpack(), ['owner.desktop'])
            self.assertIn('/owner-shortcut/', store[media]['custom-keybindings'].unpack())
            self.assertEqual(store[power]['sleep-inactive-ac-type'].unpack(), 'nothing')
            store[interface]['icon-theme'] = Value('LaterChoice')
            defaults.apply_once(state, Settings, lambda kind, value: Value(value), 'other.desktop')
            self.assertEqual(store[interface]['icon-theme'].unpack(), 'LaterChoice')
            backup = next(state.glob('desktop-before-*.json'))
            defaults.restore(json.loads(backup.read_text()), Settings,
                             lambda value: Value(ast.literal_eval(value)))
            self.assertEqual(store[interface]['icon-theme'].unpack(), 'OwnerIcons')
            self.assertEqual(store[media]['custom-keybindings'].unpack(), ['/owner-shortcut/'])
            self.assertEqual(store['org.gnome.shell']['favorite-apps'].unpack(), ['owner.desktop'])
            self.assertEqual(store[power]['sleep-inactive-ac-type'].unpack(), 'nothing')

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
        for key in ('GTK_THEME', 'GDK_SCALE', 'QT_QPA_PLATFORMTHEME',
                    'HYPRLAND_INSTANCE_SIGNATURE', 'KDE_FULL_SESSION'):
            self.assertNotIn(key, actual)
        for key in ('GTK_IM_MODULE', 'QT_IM_MODULE', 'SDL_IM_MODULE', 'INPUT_METHOD'):
            self.assertEqual(actual[key], '')
        self.assertEqual(actual['XMODIFIERS'], '@im=ibus')
        self.assertEqual(actual['QT_IM_MODULES'], 'wayland;ibus')

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
