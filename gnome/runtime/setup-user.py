#!/usr/bin/env python3
"""Keep Hyprland helpers out of GNOME without masking other desktops."""
from datetime import datetime
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
    state = home / '.local/state/omarchy-gnome'
    state.mkdir(parents=True, exist_ok=True)
    (state / 'configured').write_text(datetime.now().isoformat() + '\n')


if __name__ == '__main__':
    if os.geteuid() == 0:
        raise SystemExit('Run setup-user.py as the desktop account')
    configure(Path.home())
