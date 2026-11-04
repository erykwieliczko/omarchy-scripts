#!/usr/bin/env python3
"""Configure password login and the target user's GNOME session preference."""
import configparser
from pathlib import Path
import subprocess
import sys


def update_config(path, groups):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if path.exists():
        parser.read(path)
    for section, values in groups.items():
        if not parser.has_section(section):
            parser.add_section(section)
        parser[section].update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        parser.write(stream, space_around_delimiters=False)
    path.chmod(0o600)


def configure(root):
    update_config(root / 'etc/gdm/custom.conf', {
        'daemon': {'AutomaticLoginEnable': 'false', 'TimedLoginEnable': 'false'},
    })


def set_user_session(account):
    # Use AccountsService's API, including when it already caches another desktop.
    result = subprocess.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                             '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                             'FindUserByName', 's', account], check=True,
                            capture_output=True, text=True)
    path = result.stdout.split('"')[1]
    result = subprocess.run(['busctl', '--system', 'introspect', 'org.freedesktop.Accounts',
                             path, 'org.freedesktop.Accounts.User'],
                            check=True, capture_output=True, text=True)
    for name, value in (('SetSession', 'omarchy-gnome'), ('SetXSession', 'omarchy-gnome'),
                        ('SetSessionType', 'wayland')):
        if any(line.split() and line.split()[0] == '.' + name for line in result.stdout.splitlines()):
            subprocess.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                            path, 'org.freedesktop.Accounts.User', name, 's', value], check=True)


if __name__ == '__main__':
    configure(Path('/'))
    set_user_session(sys.argv[1])
