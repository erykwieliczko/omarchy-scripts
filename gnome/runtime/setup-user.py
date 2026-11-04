#!/usr/bin/env python3
"""Keep Hyprland helpers out of GNOME without masking other desktops."""
from datetime import datetime
import configparser
import os
from pathlib import Path


def configure(home):
    generator = home / '.config/systemd/user-environment-generators/90-omarchy-gnome'
    generator.parent.mkdir(parents=True, exist_ok=True)
    generator.unlink(missing_ok=True)
    generator.symlink_to('/usr/local/lib/omarchy-gnome/environment-generator')
    for name in ('owed', 'bt-agent', 'omarchy-sleep-lock',
                 'omarchy-recover-internal-monitor', 'omarchy-crash-watch',
                 'omarchy-migrate-notify', 'omarchy-fcitx5'):
        dropin = home / f'.config/systemd/user/{name}.service.d/90-omarchy-gnome.conf'
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text('[Unit]\nConditionEnvironment=!XDG_CURRENT_DESKTOP=GNOME\n')
    # gnome-session can also launch Fcitx through XDG autostart, independently
    # of the supervised service. Its IBus compatibility interface blocks GNOME's
    # own IBus daemon. Preserve autostart in other desktops.
    target = home / '.config/autostart/org.fcitx.Fcitx5.desktop'
    source = target if target.exists() else Path('/etc/xdg/autostart/org.fcitx.Fcitx5.desktop')
    if source.exists():
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(source)
        section = parser['Desktop Entry']
        excluded = [name for name in section.get('NotShowIn', '').split(';') if name]
        if 'GNOME' not in excluded:
            if target.exists():
                backup = target.with_suffix('.desktop.pre-omarchy-gnome')
                if not backup.exists():
                    backup.write_text(target.read_text())
            section['NotShowIn'] = ';'.join(excluded + ['GNOME']) + ';'
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('w') as stream:
                parser.write(stream, space_around_delimiters=False)
    state = home / '.local/state/omarchy-gnome'
    state.mkdir(parents=True, exist_ok=True)
    (state / 'configured').write_text(datetime.now().isoformat() + '\n')


if __name__ == '__main__':
    if os.geteuid() == 0:
        raise SystemExit('Run setup-user.py as the desktop account')
    configure(Path.home())
