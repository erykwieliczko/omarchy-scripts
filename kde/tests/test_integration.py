import configparser
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNTIME = Path(__file__).parents[1] / 'runtime'


def module(name):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class KDEIntegration(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
