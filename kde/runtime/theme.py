#!/usr/bin/env python3
"""Import the current Omarchy palette and wallpaper into native KDE settings."""
import argparse
import configparser
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tomllib


def wait_for_desktop(timeout=15):
    # Plasma owns its D-Bus name before it creates the initial desktop layout.
    # Applying a wallpaper to an empty desktops() list reports success but has
    # no effect on a fresh profile. Wait for the layout, not a fixed delay.
    deadline = time.monotonic() + timeout
    while True:
        result = subprocess.run(
            ['busctl', '--user', '--timeout=2', 'call', 'org.kde.plasmashell',
             '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', 's',
             'print(desktops().length)'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.startswith('s '):
            if int(json.loads(result.stdout[2:])) > 0:
                return
        if time.monotonic() >= deadline:
            raise RuntimeError('Plasma did not finish creating its desktop layout')
        time.sleep(0.1)


def make_scheme(colors, base):
    scheme = configparser.ConfigParser(interpolation=None)
    scheme.optionxform = str
    scheme.read_string(base)

    def rgb(key, default):
        value = colors.get(key, default)
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError(f'Invalid Omarchy color: {key}')
        return ','.join(str(int(value[i:i + 2], 16)) for i in (1, 3, 5))

    background = rgb('background', '#1a1b26')
    foreground = rgb('foreground', '#c0caf5')
    accent = rgb('accent', '#7aa2f7')
    muted = rgb('dark_foreground', '#565f89')
    for section in scheme.sections():
        if not section.startswith('Colors:'):
            continue
        group = scheme[section]
        group['BackgroundNormal'] = background
        group['BackgroundAlternate'] = rgb('lighter_background', '#24283b')
        group['ForegroundNormal'] = foreground
        group['ForegroundInactive'] = muted
        group['ForegroundActive'] = accent
        group['DecorationFocus'] = accent
        group['DecorationHover'] = accent
        for key, color in (('ForegroundLink', 'blue'), ('ForegroundVisited', 'magenta'),
                           ('ForegroundNegative', 'red'), ('ForegroundPositive', 'green'),
                           ('ForegroundNeutral', 'yellow')):
            group[key] = rgb(color, '#7aa2f7')
    scheme['Colors:View']['BackgroundNormal'] = rgb('dark_background', '#13141c')
    scheme['Colors:Selection']['BackgroundNormal'] = accent
    scheme['Colors:Selection']['ForegroundNormal'] = background
    scheme['General']['Name'] = 'Omarchy'
    scheme['General']['ColorScheme'] = 'Omarchy'
    scheme['WM']['activeBackground'] = background
    scheme['WM']['activeForeground'] = foreground
    scheme['WM']['inactiveBackground'] = background
    scheme['WM']['inactiveForeground'] = muted
    return scheme


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='write the palette without changing the live desktop')
    args = parser.parse_args()
    home = Path.home()
    current = home / '.local/state/omarchy/current'
    palette = current / 'theme/colors.toml'
    if palette.exists():
        colors = tomllib.loads(palette.read_text())
        vendor = Path('/usr/share/color-schemes/BreezeLight.colors' if colors.get('mode') == 'light'
                      else '/usr/share/color-schemes/BreezeDark.colors')
        scheme = make_scheme(colors, vendor.read_text())
        target = home / '.local/share/color-schemes/Omarchy.colors'
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w') as stream:
            # The generated scheme retains the base scheme's attribution.
            for line in vendor.read_text().splitlines():
                if line.startswith('# SPDX-'):
                    stream.write(line + '\n')
            scheme.write(stream, space_around_delimiters=False)
    if args.prepare:
        return
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    if palette.exists():
        subprocess.run(['plasma-apply-colorscheme', 'Omarchy'], env=environment, check=True)
    wallpaper = current / 'background'
    if wallpaper.is_file():
        wait_for_desktop()
        subprocess.run(['plasma-apply-wallpaperimage', str(wallpaper.resolve())],
                       env=environment, check=True)


if __name__ == '__main__':
    main()
