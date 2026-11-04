#!/usr/bin/env python3
"""Seed a complete GNOME profile once, without changing power or lock policy."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def profile(browser):
    return {
        'org.gnome.desktop.interface': {
            'color-scheme': 'prefer-dark', 'gtk-theme': 'Adwaita-dark',
            'icon-theme': 'Adwaita', 'cursor-theme': 'Adwaita',
            'show-battery-percentage': True, 'clock-show-weekday': True,
        },
        'org.gnome.desktop.peripherals.touchpad': {
            'tap-to-click': True, 'natural-scroll': True, 'click-method': 'fingers',
            'two-finger-scrolling-enabled': True, 'disable-while-typing': True,
        },
        'org.gnome.desktop.wm.preferences': {
            'button-layout': ':minimize,maximize,close',
        },
        'org.gnome.desktop.wm.keybindings': {
            'switch-applications': ['<Super>Tab'],
            'switch-applications-backward': ['<Shift><Super>Tab'],
            'switch-windows': ['<Alt>Tab'],
            'switch-windows-backward': ['<Shift><Alt>Tab'],
        },
        'org.gnome.shell.window-switcher': {'current-workspace-only': False},
        'org.gnome.settings-daemon.plugins.media-keys': {'home': ['<Super>e']},
        'org.gnome.mutter': {'dynamic-workspaces': True, 'edge-tiling': True},
        'org.gnome.shell': {
            'favorite-apps': [browser, 'org.gnome.Nautilus.desktop',
                              'org.gnome.Console.desktop', 'org.gnome.TextEditor.desktop',
                              'org.gnome.Software.desktop', 'org.gnome.Settings.desktop'],
        },
    }


def restore(values, settings_for, parse_variant):
    for schema, keys in values.items():
        settings = settings_for(schema)
        for key, value in keys.items():
            if value is None:
                settings.reset(key)
            elif not settings.set_value(key, parse_variant(value)):
                raise RuntimeError(f'Could not restore {schema} {key}')


def apply_once(state, settings_for, make_variant, browser):
    marker = state / 'desktop-defaults-v1'
    if marker.exists():
        print('GNOME desktop defaults already applied; keeping your preferences.')
        return
    desired = profile(browser)
    shell = settings_for('org.gnome.shell')
    extensions = list(shell.get_value('enabled-extensions').unpack())
    indicator = 'appindicatorsupport@rgcjonas.gmail.com'
    if indicator not in extensions:
        extensions.append(indicator)
    desired['org.gnome.shell']['enabled-extensions'] = extensions
    media_schema = 'org.gnome.settings-daemon.plugins.media-keys'
    paths = list(settings_for(media_schema).get_value('custom-keybindings').unpack())
    for name, binding in (('terminal', '<Super>Return'), ('terminal-alt', '<Control><Alt>t')):
        path = f'/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/omarchy-gnome-{name}/'
        if path not in paths:
            paths.append(path)
        desired[media_schema + '.custom-keybinding:' + path] = {
            'name': 'Open GNOME Console', 'command': 'kgx', 'binding': binding,
        }
    desired[media_schema]['custom-keybindings'] = paths
    before = {}
    for schema, keys in desired.items():
        settings = settings_for(schema)
        before[schema] = {}
        for key in keys:
            value = settings.get_user_value(key)
            before[schema][key] = None if value is None else value.print_(True)
    # Existing favorite apps are a deliberate preference; only replace the
    # distribution's initial favorites (which can point at missing applications).
    if before['org.gnome.shell']['favorite-apps'] is not None:
        del desired['org.gnome.shell']['favorite-apps']
        del before['org.gnome.shell']['favorite-apps']
    state.mkdir(parents=True, exist_ok=True)
    backup = state / ('desktop-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '.json')
    backup.write_text(json.dumps(before, indent=2) + '\n')
    for schema, keys in desired.items():
        settings = settings_for(schema)
        for key, value in keys.items():
            kind = settings.get_value(key).get_type_string()
            if not settings.set_value(key, make_variant(kind, value)):
                raise RuntimeError(f'Could not set {schema} {key}; prior values: {backup}')
    marker.write_text(str(backup) + '\n')
    print(f'GNOME desktop defaults applied. Previous values: {backup}')


def main():
    if os.geteuid() == 0:
        raise SystemExit('Run desktop-defaults.py as the desktop account')
    from gi.repository import Gio, GLib
    def settings_for(identifier):
        if ':' in identifier:
            schema, path = identifier.split(':', 1)
            return Gio.Settings.new_with_path(schema, path)
        return Gio.Settings.new(identifier)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', type=Path, help='restore the selected settings from a JSON backup')
    args = parser.parse_args()
    if args.restore:
        restore(json.loads(args.restore.read_text()), settings_for,
                lambda value: GLib.Variant.parse(None, value, None, None))
    else:
        browser = Gio.AppInfo.get_default_for_uri_scheme('https')
        apply_once(Path.home() / '.local/state/omarchy-gnome', settings_for,
                   GLib.Variant, browser.get_id() if browser else 'chromium.desktop')
    Gio.Settings.sync()


if __name__ == '__main__':
    main()
