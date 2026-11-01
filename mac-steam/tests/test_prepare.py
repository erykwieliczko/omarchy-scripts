#!/usr/bin/env python3
"""Exercise Steam updates, deferred patching and preservation of user settings."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'runtime/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class SteamUpdates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'Steam with spaces'
        self.tool = self.root / 'steamapps/common/FEX-Emu'
        self.prefix = self.base / 'private'
        self.patch = patch.object(prepare, 'PREFIX', self.prefix)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.prefix / 'fex/bin').mkdir(parents=True)
        (self.prefix / 'runtime').mkdir()
        (self.prefix / 'runtime/fex-server-manager').write_bytes(b'server lifetime wrapper')
        (self.tool / 'usr/bin').mkdir(parents=True)
        for name in ('FEX', 'FEXServer', 'FEXServerManager', 'FEXCompatTool'):
            (self.prefix / 'fex/bin' / name).write_bytes(b'patched ' + name.encode())
            target = self.tool / ('FEXCompatTool' if name == 'FEXCompatTool' else 'usr/bin/' + name)
            target.write_bytes(b'valve original')
        self.manifest = self.root / 'steamapps/appmanifest_3127680.acf'
        self.manifest.write_text('"StateFlags" "4"\n')
        (self.tool / 'ConfigTemplate.json').write_text(json.dumps({'Config': {
            'RootFS': '@FEX_ROOTFS_PATH@/', 'UserSetting': 'keep'}}))

    def test_update_is_repaired_and_original_backup_survives(self):
        seen = {}
        prepare.prepare(self.root, seen)
        target = self.tool / 'usr/bin/FEX'
        self.assertEqual(target.read_bytes(), b'patched FEX')
        self.assertEqual((self.tool / 'usr/bin/FEXServerManager').read_bytes(), b'server lifetime wrapper')
        inode = target.stat().st_ino
        prepare.prepare(self.root, seen)
        self.assertEqual(target.stat().st_ino, inode)
        replacement = target.with_name('downloaded-FEX')
        replacement.write_bytes(b'valve update')
        replacement.replace(target)
        prepare.prepare(self.root, seen)
        self.assertEqual(target.read_bytes(), b'patched FEX')
        self.assertEqual(target.with_name('FEX.valve-original').read_bytes(), b'valve original')
        self.assertEqual(json.loads((self.tool / 'ConfigTemplate.json').read_text())['Config']['UserSetting'], 'keep')

    def test_downloading_and_active_tool_are_left_alone(self):
        downloading = self.root / 'steamapps/downloading/3127680'
        downloading.mkdir(parents=True)
        prepare.prepare(self.root, {})
        self.assertEqual((self.tool / 'usr/bin/FEX').read_bytes(), b'valve original')
        downloading.rmdir()
        with patch.object(prepare, 'tool_in_use', return_value=True):
            prepare.prepare(self.root, {})
        self.assertEqual((self.tool / 'usr/bin/FEX').read_bytes(), b'valve original')
        self.manifest.write_text('"StateFlags" "1026"')
        prepare.prepare(self.root, {})
        self.assertEqual((self.tool / 'usr/bin/FEX').read_bytes(), b'valve original')

    def test_aoe_profile_preserves_other_thunks(self):
        config = self.root / 'steamapps/compatdata/813780/fex-emu'
        config.mkdir(parents=True)
        (config / 'ThunksDB.json').write_text('{"DB":{"UserThunk":{"Library":"mine.so"}}}')
        prepare.prepare(self.root, {})
        database = json.loads((config / 'ThunksDB.json').read_text())['DB']
        self.assertEqual(database['UserThunk']['Library'], 'mine.so')
        self.assertIn('/usr/lib/libvulkan.so.1', database['AoEVulkan']['Overlay'])
        app = json.loads((config / 'AppConfig/Steam_813780_AoE2DE_s.exe.json').read_text())
        self.assertEqual(app['ThunksDB']['AoEVulkan'], 1)
        self.assertFalse((self.root / 'steamapps/compatdata/1234').exists())

    def test_library_path_with_spaces(self):
        extra = self.base / 'External Steam Library'
        extra.mkdir()
        (self.root / 'steamapps/libraryfolders.vdf').write_text('"path" "' + str(extra) + '"\n')
        self.assertEqual(prepare.libraries(self.root), [self.root, extra])

    def test_native_driver_selection_is_personalized_and_restored_after_update(self):
        template_path = self.tool / 'ConfigTemplate.json'
        original = json.loads(template_path.read_text())
        original['AppOverrides'] = {
            'AoE2DE_s.exe': {'UserSetting': 'keep'},
            'Other.exe': {'UserSetting': 'other'},
        }
        template_path.write_text(json.dumps(original))
        for attempt in range(2):
            prepare.prepare(self.root, {})
            # Match Valve's personalization step, including a library path with spaces.
            template = json.loads(template_path.read_text().replace('@FEX_COMPAT_TOOL@', str(self.tool)))
            aoe = template['AppOverrides']['AoE2DE_s.exe']
            self.assertEqual(aoe['UserSetting'], 'keep')
            self.assertEqual(template['AppOverrides']['Other.exe']['UserSetting'], 'other')
            self.assertIsInstance(aoe['HostEnv'], str)
            name, value = aoe['HostEnv'].split('=', 1)
            self.assertEqual(name, 'VK_DRIVER_FILES')
            native_icd = Path(value)
            driver = json.loads(native_icd.read_text())['ICD']
            self.assertEqual(driver['library_path'], '/run/host/usr/lib/libvulkan_asahi.so')
            if attempt == 0:
                template_path.write_text(json.dumps(original))
                native_icd.unlink()

    def install_game_fixture(self, library=None):
        library = library or self.root
        game = library / 'steamapps/common/AoE2DE'
        game.mkdir(parents=True)
        (game / 'AoE2DE_s.exe').write_bytes(b'game fixture')
        manifest = library / 'steamapps/appmanifest_813780.acf'
        manifest.write_text('"StateFlags" "4"\n')
        return game, manifest

    def test_dxvk_waits_for_complete_game_then_installs_once(self):
        game, manifest = self.install_game_fixture()
        manifest.write_text('"StateFlags" "1026"\n')
        prepare.prepare(self.root, {})
        config = game / 'dxvk.conf'
        self.assertFalse(config.exists())
        manifest.write_text('"StateFlags" "4"\n')
        downloading = self.root / 'steamapps/downloading/813780'
        downloading.mkdir(parents=True)
        prepare.prepare(self.root, {})
        self.assertFalse(config.exists())
        downloading.rmdir()
        prepare.prepare(self.root, {})
        self.assertIn('dxgi.maxFrameLatency = 1\n', config.read_text())
        inode, modified = config.stat().st_ino, config.stat().st_mtime_ns
        prepare.prepare(self.root, {})
        self.assertEqual((config.stat().st_ino, config.stat().st_mtime_ns), (inode, modified))

    def test_dxvk_preserves_settings_comments_and_original_backup(self):
        game, _ = self.install_game_fixture()
        config = game / 'dxvk.conf'
        original = '# dxgi.maxFrameLatency = 0\ndxvk.hud = fps\n[Other.exe]\ndxgi.syncInterval = 0\n'
        config.write_text(original)
        config.chmod(0o600)
        prepare.prepare(self.root, {})
        self.assertTrue(config.read_text().endswith(original))
        self.assertIn('\ndxgi.maxFrameLatency = 1\n', config.read_text())
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        backup = config.with_name('dxvk.conf.pre-ultimate')
        self.assertEqual(backup.read_text(), original)
        prepare.prepare(self.root, {})
        self.assertEqual(backup.read_text(), original)

    def test_dxvk_respects_explicit_user_latency_and_symlink(self):
        game, _ = self.install_game_fixture()
        config = game / 'dxvk.conf'
        for value in (0, 3):
            original = f'[AoE2DE_s.exe]\n  dxgi.maxFrameLatency = {value}\n'
            config.write_text(original)
            prepare.prepare(self.root, {})
            self.assertEqual(config.read_text(), original)
            self.assertFalse(config.with_name('dxvk.conf.pre-ultimate').exists())
        config.unlink()
        outside = self.base / 'custom-dxvk.conf'
        outside.write_text('dxvk.hud = fps\n')
        config.symlink_to(outside)
        prepare.prepare(self.root, {})
        self.assertTrue(config.is_symlink())
        self.assertEqual(outside.read_text(), 'dxvk.hud = fps\n')

    def test_dxvk_follows_external_game_library_without_touching_absent_games(self):
        external = self.base / 'External Steam library'
        game, _ = self.install_game_fixture(external)
        (self.root / 'steamapps/libraryfolders.vdf').write_text(f'"path" "{external}"\n')
        prepare.prepare(self.root, {})
        self.assertIn('dxgi.maxFrameLatency = 1\n', (game / 'dxvk.conf').read_text())
        self.assertFalse((self.root / 'steamapps/common/AoE2DE').exists())


if __name__ == '__main__':
    unittest.main()
