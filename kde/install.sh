#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")" && pwd)
account=${SUDO_USER:-}
activate=0
check_only=0
while (( $# )); do
    case $1 in
        --user) account=${2:?--user needs a desktop account}; shift 2 ;;
        --activate) activate=1; shift ;;
        --check) check_only=1; shift ;;
        --help|-h)
            printf '%s\n' 'Install Mac KDE Ultimate WIP' \
                'Usage: install.sh [--user ACCOUNT] [--check] [--activate]' \
                'Installs KDE Plasma and Plasma Login Manager, with password login.' \
                '--activate ends the current graphical session after installation.'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
die() { echo "Omarchy KDE: $*" >&2; exit 1; }
[[ $(uname -m) == aarch64 && -f /etc/arch-release ]] || die 'Requires Omarchy/Arch Linux ARM on Apple Silicon.'
[[ -r /proc/device-tree/compatible ]] || die 'Cannot identify this Mac.'
tr '\0' '\n' < /proc/device-tree/compatible | grep -qx 'apple,arm-platform' || die 'Requires an Apple Silicon Mac.'
[[ -x /usr/bin/omarchy ]] || die 'Omarchy must be installed first.'
if [[ -z $account && $EUID != 0 ]]; then account=$(id -un); fi
if [[ -z $account ]]; then
    account=$(loginctl list-sessions --no-legend | awk '$2 >= 1000 && $4 == "seat0" && $3 != "root" {print $3; exit}')
fi
[[ -n $account && $account != root ]] || die 'Use --user YOUR_DESKTOP_ACCOUNT.'
uid=$(id -u "$account")
(( uid >= 1000 )) || die 'The desktop account must be a regular user.'
home_dir=$(getent passwd "$account" | cut -d: -f6)
[[ -d $home_dir ]] || die 'Desktop home directory is missing.'
printf 'Omarchy KDE: account %s, kernel %s\n' "$account" "$(uname -r)"
if (( check_only )); then
    echo 'Platform and desktop-account checks passed.'
    exit 0
fi
(( EUID == 0 )) || die 'Use the bootstrap installer; it invokes sudo.'
exec 9>/run/lock/omarchy-kde-install.lock
flock -n 9 || die 'Another KDE installation is running.'
backup=/var/lib/omarchy-kde/backups/$(date +%Y%m%dT%H%M%S)-$$
install -d -m700 "$backup"
for path in /etc/plasmalogin.conf /etc/plasmalogin.conf.d /etc/sddm.conf /etc/sddm.conf.d \
    /etc/systemd/system/display-manager.service /etc/systemd/system/plasmalogin.service.d; do
    if [[ -e $path || -L $path ]]; then
        cp -a --parents "$path" "$backup/"
    fi
done
# Repository metadata belongs to Omarchy's normal update flow. Do not run pacman -Sy here.
pacman -S --needed --noconfirm plasma-meta plasma-login-manager dolphin konsole kate ark \
    spectacle kwallet-pam python
install -d -m755 /usr/local/lib/omarchy-kde/bin /usr/local/bin /usr/local/share/wayland-sessions
for file in start-plasma session-env.sh theme.py setup-user.py switch-desktop steam-native-messaging-stub; do
    install -m755 "$project/runtime/$file" "/usr/local/lib/omarchy-kde/$file"
done
for file in uwsm-app omarchy; do
    install -m755 "$project/runtime/$file" "/usr/local/lib/omarchy-kde/bin/$file"
done
ln -sfn /usr/local/lib/omarchy-kde/theme.py /usr/local/bin/omarchy-kde-sync-theme
cat > /usr/local/share/wayland-sessions/omarchy-plasma.desktop <<'EOF'
[Desktop Entry]
Name=Omarchy (KDE Plasma)
Comment=KDE Plasma with Omarchy applications and theme integration
Exec=/usr/local/lib/omarchy-kde/start-plasma
TryExec=/usr/bin/startplasma-wayland
DesktopNames=KDE
Type=Application
EOF
python3 - "$account" <<'PY'
import configparser, pathlib, sys
path = pathlib.Path('/etc/plasmalogin.conf')
config = configparser.ConfigParser(interpolation=None, strict=False)
config.optionxform = str
config.read(path)
for group, values in {
    'Autologin': {'User': '', 'Session': '', 'Relogin': 'false'},
    'Greeter': {'PreselectedUser': sys.argv[1], 'PreselectedSession': 'omarchy-plasma.desktop'},
}.items():
    if not config.has_section(group):
        config.add_section(group)
    config[group].update(values)
with path.open('w') as stream:
    config.write(stream, space_around_delimiters=False)
PY
install -d /etc/sddm.conf.d
cat > /etc/sddm.conf.d/zz-omarchy-kde-no-autologin.conf <<'EOF'
# Keep password login even if SDDM is selected again as a fallback.
[Autologin]
User=
Session=
Relogin=false
EOF
# Carry over Omarchy's Apple display readiness and first-boot gating.
if [[ -x /usr/lib/omarchy-mac/wait-for-display ]]; then
    install -d /etc/systemd/system/plasmalogin.service.d
    cat > /etc/systemd/system/plasmalogin.service.d/10-omarchy-mac.conf <<'EOF'
[Unit]
After=omarchy-mac-first-boot.service
ConditionPathExists=!/var/lib/omarchy/mac-first-boot/pending
ConditionPathExists=!/run/omarchy-first-boot/no-desktop

[Service]
ExecStartPre=-/usr/lib/omarchy-mac/wait-for-display
EOF
fi
install -d /usr/local/lib/systemd/user
cat > /usr/local/lib/systemd/user/omarchy-kde-theme.service <<'EOF'
[Unit]
Description=Sync the current Omarchy theme into KDE Plasma
ConditionEnvironment=XDG_CURRENT_DESKTOP=KDE
After=plasma-plasmashell.service
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/omarchy-kde-sync-theme

[Install]
WantedBy=plasma-workspace.target
EOF
cat > /usr/local/lib/systemd/user/omarchy-kde-theme.path <<'EOF'
[Unit]
Description=Watch for Omarchy theme changes in KDE
PartOf=graphical-session.target

[Path]
PathChanged=%h/.local/state/omarchy/current/theme.generation
Unit=omarchy-kde-theme.service

[Install]
WantedBy=plasma-workspace.target
EOF
as_user=(runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$uid" "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus")
"${as_user[@]}" python3 /usr/local/lib/omarchy-kde/setup-user.py
if [[ -S /run/user/$uid/bus ]]; then
    "${as_user[@]}" systemctl --user daemon-reload
    "${as_user[@]}" systemctl --user enable omarchy-kde-theme.service omarchy-kde-theme.path
else
    install -d -o "$account" -g "$(id -gn "$account")" "$home_dir/.config/systemd/user/plasma-workspace.target.wants"
    for kind in service path; do
        runuser -u "$account" -- ln -sfn "/usr/local/lib/systemd/user/omarchy-kde-theme.$kind" \
            "$home_dir/.config/systemd/user/plasma-workspace.target.wants/omarchy-kde-theme.$kind"
    done
fi
systemctl daemon-reload
systemctl disable sddm.service 2>/dev/null || :
systemctl enable --force plasmalogin.service
systemctl set-default graphical.target
echo 'Installed KDE Plasma with Plasma Login Manager and password login.'
echo "Backups: $backup"
if (( activate )); then
    systemd-run --quiet --collect --on-active=8s --unit="omarchy-kde-switch-$(date +%s)" \
        /usr/local/lib/omarchy-kde/switch-desktop "$account"
    echo 'Switching to the KDE login screen in 8 seconds. The current graphical session will close.'
else
    echo 'Reboot when ready, or rerun with --activate to switch to the KDE login screen.'
fi
