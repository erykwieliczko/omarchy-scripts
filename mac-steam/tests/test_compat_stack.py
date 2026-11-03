"""Check custom stack isolation, registration and Steam default preservation."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

RUNTIME = Path(__file__).parents[1] / 'runtime'
spec = importlib.util.spec_from_file_location('compat_stack', RUNTIME / 'compat_stack.py')
stack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stack)
loader = importlib.machinery.SourceFileLoader('mac_proton', str(RUNTIME / 'mac-proton'))
spec = importlib.util.spec_from_loader(loader.name, loader)
launcher = importlib.util.module_from_spec(spec)
loader.exec_module(launcher)


class CustomStack(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'Steam with spaces'
        self.prefix = self.base / 'private'
        common = self.root / 'steamapps/common'
        for appid, dirname in ((3127680, 'FEX-Emu'), (1493710, 'Proton - Experimental'),
                               (4183110, 'SteamLinuxRuntime_4')):
            (common / dirname).mkdir(parents=True)
            (self.root / f'steamapps/appmanifest_{appid}.acf').write_text('"StateFlags" "4"')
        self.proton = common / 'Proton - Experimental'
        driver = self.proton / 'files/lib/wine/x86_64-unix/winex11.so'
        driver.parent.mkdir(parents=True)
        driver.write_bytes(b'original')
        driver.chmod(0o555)
        (driver.parent / 'ntdll.so').write_bytes(b'ABI')
        (self.proton / 'version').write_text('qualified version\n')
        (self.proton / 'user_settings.py').write_text('private overrides')
        (common / 'SteamLinuxRuntime_4/VERSIONS.txt').write_text('qualified runtime')
        (common / 'FEX-Emu/usr/bin').mkdir(parents=True)
        (self.prefix / 'wine-focus').mkdir(parents=True)
        sha = lambda data: hashlib.sha256(data).hexdigest()
        (self.prefix / 'wine-focus/manifest.json').write_text(json.dumps({
            'proton_version': 'qualified version', 'original_sha256': sha(b'original'),
            'patched_sha256': sha(b'fixed'),
            'companions': {'files/lib/wine/x86_64-unix/ntdll.so': sha(b'ABI')},
        }))
        (self.prefix / 'wine-focus/winex11.so').write_bytes(b'fixed')
        (self.prefix / 'fex/bin').mkdir(parents=True)
        for name in ('FEX', 'FEXServer', 'FEXServerManager', 'FEXCompatTool'):
            (self.prefix / 'fex/bin' / name).write_bytes(b'private ' + name.encode())
        (self.prefix / 'runtime').mkdir()
        for name in ('mac-proton', 'fex-server-manager'):
            (self.prefix / 'runtime' / name).write_bytes((RUNTIME / name).read_bytes())
        self.config = self.root / 'config/config.vdf'
        self.config.parent.mkdir()
        self.original = ('"InstallConfigStore" { "Software" { "Valve" { "Steam" {\n'
                         '"Unrelated" "literal { brace } and \\\"quote\\\"" // comment\n'
                         '"CompatToolMapping" { "0" { "name" "old" } '
                         '"813780" { "name" "proton_experimental" } '
                         '"123" { "name" "user choice" } } } } } }\n')
        self.config.write_text(self.original)

    def test_copy_is_independent_pinned_and_preserves_valve_install(self):
        with patch.object(stack, 'steam_running', return_value=True):
            tool = stack.prepare(self.root, [self.root], self.prefix)
        self.assertIsNotNone(tool)
        self.assertEqual((tool / 'proton/files/lib/wine/x86_64-unix/winex11.so').read_bytes(), b'fixed')
        self.assertEqual((self.proton / 'files/lib/wine/x86_64-unix/winex11.so').read_bytes(), b'original')
        self.assertFalse((tool / 'proton/user_settings.py').exists())
        self.assertEqual(self.config.read_text(), self.original)
        self.assertTrue((tool / 'default-pending').exists())
        (self.proton / 'version').write_text('future Valve update')
        with patch.object(stack, 'steam_running', return_value=True):
            self.assertEqual(stack.prepare(self.root, [self.root], self.prefix), tool)
        self.assertEqual((tool / 'proton/version').read_text(), 'qualified version\n')

    def test_default_waits_for_steam_exit_and_retains_other_settings(self):
        with patch.object(stack, 'steam_running', return_value=True):
            tool = stack.prepare(self.root, [self.root], self.prefix)
        with patch.object(stack, 'steam_running', return_value=False):
            self.assertTrue(stack.set_default(self.root, tool))
        new = self.config.read_text()
        self.assertIn('"Unrelated" "literal { brace } and \\\"quote\\\"" // comment', new)
        self.assertIn('"123" { "name" "user choice" }', new)
        self.assertEqual(new.count('"name"\t\t"' + stack.TOOL_NAME + '"'), 2)
        self.assertEqual(self.config.with_name('config.vdf.pre-mac-stack').read_text(), self.original)
        self.assertFalse((tool / 'default-pending').exists())
        self.assertEqual(stack.default_config(new), new)

    def test_unqualified_or_downloading_components_are_not_registered(self):
        (self.proton / 'version').write_text('unknown ABI')
        self.assertIsNone(stack.prepare(self.root, [self.root], self.prefix))
        (self.proton / 'version').write_text('qualified version')
        (self.root / 'steamapps/downloading/4183110').mkdir(parents=True)
        self.assertIsNone(stack.prepare(self.root, [self.root], self.prefix))

    def test_new_mapping_preserves_explicit_game_override(self):
        text = '"Steam" { "Other" "keep" }'
        updated = stack.default_config(text)
        self.assertIn('"CompatToolMapping"', updated)
        self.assertIn('"Other" "keep"', updated)
        text = self.original.replace('proton_experimental', 'deliberate custom tool')
        self.assertIn('"813780" { "name" "deliberate custom tool" }', stack.default_config(text))

    def test_launcher_preserves_argument_boundaries_and_all_tool_paths(self):
        root = Path('/Steam Library/our tool')
        env = {'STEAM_COMPAT_TOOL_PATHS': '/other tool:/Steam Library/our tool'}
        argv = launcher.command(root, ['waitforexitandrun', '/game dir/game.exe', 'a $literal argument'], env)
        self.assertEqual(argv[-3:], ['waitforexitandrun', '/game dir/game.exe', 'a $literal argument'])
        self.assertEqual(argv[1], 'waitforexitandrun')
        self.assertEqual(env['STEAM_COMPAT_TOOL_PATHS'].split(':').count(str(root)), 1)
        self.assertIn('/other tool', env['STEAM_COMPAT_TOOL_PATHS'].split(':'))
        argv = launcher.command(root, ['getcompatpath', '/game dir'], {})
        self.assertEqual(argv[1], 'run')
        self.assertEqual(argv[-2:], ['getcompatpath', '/game dir'])

    def bundle(self, build='r1'):
        directory = self.prefix / 'compat-stack'
        directory.mkdir(exist_ok=True)
        (directory / 'stack.json').write_text(json.dumps({'format': 1, 'build_id': build, 'name': stack.DISPLAY_NAME}))
        (directory / 'compatibilitytool.vdf').write_text(stack.TOOL_NAME)
        (directory / 'mac-proton').write_text('independent payload')
        return directory

    def pe(self, machine):
        data = bytearray(72)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 64)
        data[64:68] = b'PE\0\0'
        struct.pack_into('<H', data, 68, machine)
        return data

    def prefix_dll(self, machine=0xaa64):
        directory = self.root / 'steamapps/compatdata/813780'
        dll = directory / 'pfx/drive_c/windows/system32/vcruntime140.dll'
        dll.parent.mkdir(parents=True)
        dll.write_bytes(self.pe(machine))
        save = directory / 'pfx/drive_c/users/steamuser/Games/Age of Empires 2 DE/savegame.aoe2save'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'original save')
        return directory, dll, save

    def test_bundle_installs_before_first_steam_launch_without_valve_tools(self):
        self.bundle()
        self.config.unlink()
        with patch.object(stack, 'steam_running', return_value=False):
            tool = stack.prepare(self.root, [], self.prefix)
        self.assertTrue((tool / 'compatibilitytool.vdf').is_file())
        self.assertIn(stack.TOOL_NAME, self.config.read_text())
        self.assertFalse((tool / 'default-pending').exists())
        self.assertEqual(os.stat(self.config).st_mode & 0o777, 0o600)

    def test_old_bundle_repairs_cloud_registration_and_only_legacy_selections(self):
        bundle = self.bundle()
        (bundle / 'compatibilitytool.vdf').write_text('"' + stack.LEGACY_TOOL_NAME + '"')
        old = self.original.replace('"old"', '"' + stack.LEGACY_TOOL_NAME + '"')
        old = old.replace('proton_experimental', stack.LEGACY_TOOL_NAME)
        old = old.replace('"user choice"', '"' + stack.LEGACY_TOOL_NAME + '"')
        self.config.write_text(old)
        with patch.object(stack, 'steam_running', return_value=False):
            tool = stack.prepare(self.root, [], self.prefix)
        self.assertEqual((tool / 'compatibilitytool.vdf').read_text(), '"' + stack.TOOL_NAME + '"')
        new = self.config.read_text()
        self.assertIn('"123" { "name" "' + stack.TOOL_NAME + '" }', new)
        self.assertIn('"Unrelated" "literal { brace } and \\\"quote\\\"" // comment', new)
        # A later upgrade must respect a deliberately changed default and app choice.
        manual = self.original.replace('proton_experimental', 'other proton')
        self.config.write_text(manual)
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [], self.prefix)
        self.assertEqual(self.config.read_text(), manual)

    def test_cloud_registration_migration_waits_for_steam_and_preserves_modes(self):
        self.bundle()
        with patch.object(stack, 'steam_running', return_value=False):
            tool = stack.prepare(self.root, [], self.prefix)
        registration = tool / 'compatibilitytool.vdf'
        registration.write_text('"' + stack.LEGACY_TOOL_NAME + '"')
        old = self.original.replace('"old"', '"' + stack.LEGACY_TOOL_NAME + '"')
        self.config.write_text(old)
        self.config.chmod(0o600)
        with patch.object(stack, 'steam_running', return_value=True):
            stack.prepare(self.root, [], self.prefix)
        self.assertEqual(self.config.read_text(), old)
        self.assertIn('"' + stack.LEGACY_TOOL_NAME + '"', registration.read_text())
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [], self.prefix)
        self.assertIn(stack.TOOL_NAME, self.config.read_text())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_cloud_registration_failure_restores_previous_metadata(self):
        self.bundle()
        with patch.object(stack, 'steam_running', return_value=False):
            tool = stack.prepare(self.root, [], self.prefix)
        registration = tool / 'compatibilitytool.vdf'
        registration.write_text('"' + stack.LEGACY_TOOL_NAME + '"')
        old = self.original.replace('"old"', '"' + stack.LEGACY_TOOL_NAME + '"')
        self.config.write_text(old)
        original_atomic = stack.atomic
        def fail_config(path, *args, **kwargs):
            if path == self.config:
                raise OSError('simulated write failure')
            return original_atomic(path, *args, **kwargs)
        with patch.object(stack, 'steam_running', return_value=False), \
                patch.object(stack, 'atomic', side_effect=fail_config):
            with self.assertRaisesRegex(OSError, 'simulated write failure'):
                stack.refresh_registration(self.root, tool)
        self.assertEqual(registration.read_text(), '"' + stack.LEGACY_TOOL_NAME + '"')
        self.assertEqual(self.config.read_text(), old)

    def test_bundle_upgrade_is_deferred_then_backed_up_outside_tool_discovery(self):
        bundle = self.bundle('r1')
        with patch.object(stack, 'steam_running', return_value=False):
            tool = stack.prepare(self.root, [], self.prefix)
        self.config.write_text(self.original)
        (bundle / 'stack.json').write_text(json.dumps({'build_id': 'r2'}))
        with patch.object(stack, 'steam_running', return_value=True):
            stack.prepare(self.root, [], self.prefix)
        self.assertEqual(json.loads((tool / 'stack.json').read_text())['build_id'], 'r1')
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [], self.prefix)
        self.assertEqual(json.loads((tool / 'stack.json').read_text())['build_id'], 'r2')
        self.assertEqual(self.config.read_text(), self.original)
        self.assertEqual(len(list((self.root / 'config/mac-steam-ultimate-backups').iterdir())), 1)
        self.assertEqual(list((self.root / 'compatibilitytools.d').iterdir()), [tool])

    def test_arm64_prefix_is_preserved_and_saves_are_carried_to_clean_prefix(self):
        self.bundle()
        directory, dll, save = self.prefix_dll()
        (directory / 'fex-emu').mkdir()
        (directory / 'fex-emu/ThunksDB.json').write_text('preserved native Vulkan configuration')
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [self.root], self.prefix)
            stack.prepare(self.root, [self.root], self.prefix)
        backups = list(directory.parent.glob('813780.arm64-before-mac-stack-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / dll.relative_to(directory)).read_bytes(), self.pe(0xaa64))
        self.assertEqual(save.read_bytes(), b'original save')
        self.assertFalse(dll.exists())
        self.assertEqual((directory / 'fex-emu/ThunksDB.json').read_text(), 'preserved native Vulkan configuration')

    def test_x86_prefix_and_explicit_arm64_tool_choice_are_preserved(self):
        self.bundle()
        directory, dll, save = self.prefix_dll(0x8664)
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [self.root], self.prefix)
        self.assertTrue(dll.exists())
        self.config.write_text(self.original.replace('proton_experimental', 'proton-experimental-arm64'))
        dll.write_bytes(self.pe(0xaa64))
        with patch.object(stack, 'steam_running', return_value=False):
            stack.prepare(self.root, [self.root], self.prefix, make_default=True)
        self.assertTrue(dll.exists())
        self.assertEqual(save.read_bytes(), b'original save')

    def test_failed_save_copy_restores_the_original_prefix(self):
        directory, dll, _ = self.prefix_dll()
        self.config.write_text(stack.default_config(self.original))
        with patch.object(stack, 'steam_running', return_value=False), \
                patch.object(stack.shutil, 'copytree', side_effect=OSError('simulated full disk')):
            with self.assertRaisesRegex(OSError, 'full disk'):
                stack.migrate_aoe_prefix(self.root, [self.root])
        self.assertEqual(dll.read_bytes(), self.pe(0xaa64))
        self.assertFalse(list(directory.parent.glob('813780.arm64-before-mac-stack-*')))

    def test_release_archive_retains_required_template_and_excludes_player_state(self):
        spec = importlib.util.spec_from_file_location('build_stack', RUNTIME.parent / 'build/compat-stack.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        (self.prefix / 'fex/SOURCE.txt').write_text('qualified FEX source')
        template = self.proton / 'files/share/default_pfx/drive_c/windows/system32/d3d8.dll'
        template.parent.mkdir(parents=True)
        template.write_bytes(b'required DirectX template data')
        private = self.root / 'steamapps/compatdata/813780/private-save'
        private.parent.mkdir(parents=True)
        private.write_bytes(b'player state must not be packaged')
        runtime_log = self.root / 'steamapps/common/SteamLinuxRuntime_4/var/session.log'
        runtime_log.parent.mkdir()
        runtime_log.write_text('private session')
        output = self.base / 'stack.tar.zst'
        builder.build(self.root, self.prefix, output)
        members = subprocess.check_output(['tar', '--zstd', '-tf', str(output)], text=True).splitlines()
        self.assertIn('./proton/files/share/default_pfx/drive_c/windows/system32/d3d8.dll', members)
        self.assertFalse(any('private-save' in p or 'session.log' in p or 'user_settings.py' in p for p in members))
        metadata = json.loads(subprocess.check_output(['tar', '--zstd', '-xOf', str(output), './stack.json'], text=True))
        self.assertEqual(metadata['build_id'], builder.BUILD_ID)
        self.assertNotIn(str(self.root), json.dumps(metadata))
        registration = subprocess.check_output(['tar', '--zstd', '-xOf', str(output), './compatibilitytool.vdf'], text=True)
        tools = stack.find(stack.nodes(registration), 'compat_tools')
        self.assertIn('proton', tools['children'][0]['key'].lower())


if __name__ == '__main__':
    unittest.main()
