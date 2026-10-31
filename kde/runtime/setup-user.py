#!/usr/bin/env python3
"""Configure KDE integration as the desktop user, preserving existing settings."""
import configparser
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess


def update_config(path, groups):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if path.exists():
        parser.read(path)
        backup = path.with_name(path.name + '.pre-omarchy-kde')
        if not backup.exists():
            shutil.copy2(path, backup)
    for name, settings in groups.items():
        if not parser.has_section(name):
            parser.add_section(name)
        parser[name].update(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        parser.write(stream, space_around_delimiters=False)


def retire_focus_rule(path):
    """Remove our superseded workaround without changing other window rules."""
    if not path.exists():
        return
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path)
    if not parser.remove_section('omarchy-aoe2-focus'):
        return
    backup = path.with_name(path.name + '.pre-wine-focus-repair')
    if not backup.exists():
        shutil.copy2(path, backup)
    for key in ('Order', 'rules'):
        if parser.has_option('General', key):
            groups = parser['General'][key].split(',')
            parser['General'][key] = ','.join(g for g in groups if g != 'omarchy-aoe2-focus')
    with path.open('w') as stream:
        parser.write(stream, space_around_delimiters=False)


def main():
    if os.geteuid() == 0:
        raise SystemExit('Run setup-user.py as the desktop account.')
    home = Path.home()
    config = home / '.config'
    state = home / '.local/state/omarchy-kde'
    state.mkdir(parents=True, exist_ok=True)
    first = not (state / 'configured').exists()
    # Keep Hyprland services for Hyprland sessions; Plasma supplies its own equivalents.
    for name in ('owed', 'bt-agent', 'omarchy-sleep-lock',
                 'omarchy-recover-internal-monitor', 'omarchy-crash-watch', 'omarchy-migrate-notify'):
        dropin = config / f'systemd/user/{name}.service.d/90-omarchy-kde.conf'
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text('[Unit]\nConditionEnvironment=XDG_CURRENT_DESKTOP=Hyprland\n')
    # Omarchy's D-Bus activation points at this service. Keep it available:
    # KWin's Wayland launcher activates it and passes the input-method socket.
    (config / 'systemd/user/omarchy-fcitx5.service.d/90-omarchy-kde.conf').unlink(missing_ok=True)
    environment = config / 'plasma-workspace/env/20-omarchy-kde.sh'
    environment.parent.mkdir(parents=True, exist_ok=True)
    environment.write_text('. /usr/local/lib/omarchy-kde/session-env.sh\n')
    if Path('/usr/share/applications/fcitx5-wayland-launcher.desktop').exists():
        kwin = config / 'kwinrc'
        if kwin.exists() and not kwin.with_name('kwinrc.pre-omarchy-kde').exists():
            shutil.copy2(kwin, kwin.with_name('kwinrc.pre-omarchy-kde'))
        subprocess.run(['kwriteconfig6', '--file', 'kwinrc', '--group', 'Wayland',
                        '--key', 'InputMethod', '--notify',
                        '/usr/share/applications/fcitx5-wayland-launcher.desktop'], check=True)
    if Path('/opt/mac-steam-ultimate/current/wine-focus/manifest.json').exists():
        retire_focus_rule(config / 'kwinrulesrc')
    # Steam's CEF discovers the system Chromium extension, but its native host
    # spins inside muvm. Override only the Steam profile, preserving browser integration elsewhere.
    native_manifest = Path('/etc/chromium/native-messaging-hosts/org.kde.plasma.browser_integration.json')
    if native_manifest.exists():
        steam = home / '.steam/steam'
        steam = steam.resolve() if steam.exists() else home / '.local/share/Steam'
        target = steam / 'config/htmlcache/NativeMessagingHosts/org.kde.plasma.browser_integration.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not target.with_suffix('.json.pre-omarchy-kde').exists():
            shutil.copy2(target, target.with_suffix('.json.pre-omarchy-kde'))
        manifest = json.loads(native_manifest.read_text())
        manifest['path'] = '/usr/local/lib/omarchy-kde/steam-native-messaging-stub'
        target.write_text(json.dumps(manifest, indent=2) + '\n')
    if first:
        # These are defaults for the new KDE profile; reruns preserve later KDE choices.
        update_config(config / 'kdeglobals', {
            'General': {'ColorScheme': 'Omarchy'},
            'KDE': {'widgetStyle': 'Breeze'},
            'Icons': {'Theme': 'breeze-dark'},
        })
        update_config(config / 'ksmserverrc', {'General': {'loginMode': 'emptySession'}})
    subprocess.run(['python3', '/usr/local/lib/omarchy-kde/theme.py', '--prepare'], check=True)
    (state / 'configured').write_text(datetime.now().isoformat() + '\n')


if __name__ == '__main__':
    main()
