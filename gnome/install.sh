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
            printf '%s\n' 'Install Mac GNOME Ultimate WIP' \
                'Usage: install.sh [--user ACCOUNT] [--check] [--activate]' \
                'Installs standard GNOME, its apps, and GDM with password login.' \
                '--activate ends the current graphical session after installation.'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
die() { echo "Omarchy GNOME: $*" >&2; exit 1; }
[[ -f /etc/arch-release ]] || die 'Requires Omarchy/Arch Linux.'
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
printf 'Omarchy GNOME: account %s, kernel %s\n' "$account" "$(uname -r)"
if (( check_only )); then
    echo 'Package platform and desktop-account checks passed.'
    exit 0
fi
(( EUID == 0 )) || die 'Use the bootstrap installer; it invokes sudo.'
exec 9>/run/lock/omarchy-gnome-install.lock
flock -n 9 || die 'Another GNOME installation is running.'
backup=/var/lib/omarchy-gnome/backups/$(date +%Y%m%dT%H%M%S)-$$
install -d -m700 "$backup"
previous=$(readlink -f /etc/systemd/system/display-manager.service || :)
previous=${previous##*/}
printf '%s\n' "$previous" > "$backup/previous-manager"
for path in /etc/gdm/custom.conf /var/lib/AccountsService/users/"$account" \
    /etc/systemd/system/display-manager.service /etc/systemd/system/gdm.service.d; do
    if [[ -e $path || -L $path ]]; then cp -a --parents "$path" "$backup/"; fi
done
# shellcheck source=../common/pacman-install.sh
source "$project/../common/pacman-install.sh"
# The combined repository group can retain obsolete GNOME Books/Boxes builds
# whose removed libsoup dependency blocks the entire desktop transaction.
mac_install_packages gdm gnome-shell gnome-session gnome-settings-daemon \
    gnome-control-center gnome-keyring gnome-console gnome-text-editor nautilus \
    gnome-calculator gnome-calendar gnome-contacts gnome-clocks gnome-font-viewer \
    gnome-disk-utility gnome-logs gnome-system-monitor gnome-backgrounds gnome-tweaks \
    gnome-software gnome-user-docs yelp loupe papers showtime snapshot simple-scan \
    gnome-weather gnome-maps gnome-characters gnome-connections gnome-tour \
    seahorse baobab sushi file-roller decibels geary libreoffice-fresh gnome-remote-desktop \
    gnome-extensions-app gnome-shell-extensions gnome-shell-extension-appindicator \
    flatpak adwaita-fonts adwaita-icon-theme gst-libav gst-plugins-good \
    gst-plugins-bad gst-plugins-ugly gvfs-goa gvfs-nfs \
    xdg-desktop-portal-gnome xdg-user-dirs-gtk gvfs gvfs-mtp gvfs-smb \
    python python-gobject xorg-xwayland
install -d -m755 /usr/local/lib/omarchy-gnome/bin
for file in start-gnome session-env.sh setup-user.py desktop-defaults.py setup-flatpak-gl.py configure.py switch-desktop environment-generator; do
    install -m755 "$project/runtime/$file" "/usr/local/lib/omarchy-gnome/$file"
done
for file in omarchy uwsm-app; do
    install -m755 "$project/runtime/$file" "/usr/local/lib/omarchy-gnome/bin/$file"
done
# This entry uses stock GNOME with the old compositor's environment removed.
install -d /usr/share/wayland-sessions
cat > /usr/share/wayland-sessions/omarchy-gnome.desktop <<'EOF'
[Desktop Entry]
Name=Omarchy (GNOME)
Comment=Standard GNOME with Omarchy application integration
Exec=/usr/local/lib/omarchy-gnome/start-gnome
TryExec=/usr/bin/gnome-session
Type=Application
DesktopNames=GNOME
X-GDM-SessionRegisters=true
EOF
python3 /usr/local/lib/omarchy-gnome/configure.py "$account"
if [[ -x /usr/lib/omarchy-mac/wait-for-display ]]; then
    install -d /etc/systemd/system/gdm.service.d
    cat > /etc/systemd/system/gdm.service.d/10-omarchy-mac.conf <<'EOF'
[Unit]
After=omarchy-mac-first-boot.service
ConditionPathExists=!/var/lib/omarchy/mac-first-boot/pending
ConditionPathExists=!/run/omarchy-first-boot/no-desktop

[Service]
ExecStartPre=-/usr/lib/omarchy-mac/wait-for-display
EOF
fi
runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$uid" \
    "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" \
    python3 /usr/local/lib/omarchy-gnome/setup-user.py
runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$uid" XDG_CURRENT_DESKTOP=GNOME \
    "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" \
    python3 /usr/local/lib/omarchy-gnome/desktop-defaults.py
runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$uid" \
    "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" \
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
python3 /usr/local/lib/omarchy-gnome/setup-flatpak-gl.py "$account"
if [[ -S /run/user/$uid/bus ]]; then
    runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$uid" systemctl --user daemon-reload
fi
if [[ -n $previous && $previous != gdm.service ]]; then
    printf '%s\n' "$previous" > /var/lib/omarchy-gnome/previous-manager
fi
systemctl daemon-reload
for manager in sddm.service plasmalogin.service greetd.service; do
    systemctl disable "$manager" 2>/dev/null || :
done
systemctl enable --force gdm.service
systemctl set-default graphical.target
echo 'Installed GNOME, its standard apps, and GDM with password login.'
echo "Backups: $backup"
if (( activate )); then
    systemd-run --quiet --collect --on-active=8s --unit="omarchy-gnome-switch-$(date +%s)" \
        /usr/local/lib/omarchy-gnome/switch-desktop "$account"
    echo 'Switching to GDM in 8 seconds. The current graphical session will close.'
else
    echo 'Reboot when ready, or rerun with --activate to switch to GDM now.'
fi
