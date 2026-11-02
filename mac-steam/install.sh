#!/usr/bin/env bash
# Install Mac Steam Ultimate WIP — M1 / M3 Pro, Omarchy Apple Silicon.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")" && pwd)
release=mac-steam-ultimate-wip-v0.3.0
# Existing qualified components retain their immutable v0.2.0 download URLs.
base=https://github.com/erykwieliczko/omarchy-scripts/releases/download/mac-steam-ultimate-wip-v0.2.0
native_base=https://github.com/erykwieliczko/omarchy-scripts/releases/download/$release
target_user=${SUDO_USER:-}
cache=/var/cache/mac-steam-ultimate
check_only=0
while (( $# )); do
    case $1 in
        --user) target_user=${2:?--user needs an account name}; shift 2 ;;
        --check) check_only=1; shift ;;
        --help|-h)
            printf '%s\n' 'Install Mac Steam Ultimate WIP' \
                'Usage: install.sh [--user DESKTOP_USER] [--check]' \
                'Requires Omarchy/Arch ARM on Apple M1 (T8103) or M3 Pro (T6030).' \
                'Run from your desktop account with sudo, or specify --user as root.'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
die() { echo "Steam Ultimate: $*" >&2; exit 1; }
[[ $(uname -m) == aarch64 ]] || die 'This installer requires an ARM64 Mac running Linux.'
[[ -f /etc/arch-release ]] || die 'This installer requires Omarchy/Arch Linux ARM.'
[[ -r /proc/device-tree/compatible ]] || die 'Cannot identify the Apple Silicon hardware.'
tr '\0' '\n' < /proc/device-tree/compatible | grep -Exq 'apple,(t8103|t6030)' ||
    die 'This WIP release supports M1 (T8103) and M3 Pro (T6030).'
[[ $(getconf PAGESIZE) == 16384 ]] || die 'Expected the qualified 16K host kernel.'
for repo in omarchy asahi-alarm; do
    pacman-conf --repo-list | grep -qx "$repo" || die "Required pacman repository is missing: $repo"
done
if [[ -z $target_user && $EUID != 0 ]]; then target_user=$(id -un); fi
if [[ -z $target_user ]]; then
    target_user=$(loginctl list-sessions --no-legend | awk '$2 >= 1000 && $4 == "seat0" && $3 != "root" { print $3; exit }')
fi
[[ -n $target_user && $target_user != root ]] || die 'Use --user YOUR_DESKTOP_ACCOUNT.'
uid=$(id -u "$target_user")
(( uid >= 1000 )) || die 'The target must be a regular desktop account.'
user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -d $user_home && $user_home == /* ]] || die 'The desktop home directory does not exist.'
printf 'Target: %s (%s), kernel %s\n' "$target_user" "$user_home" "$(uname -r)"
m3=0
if tr '\0' '\n' < /proc/device-tree/compatible | grep -qx apple,t6030; then
    tr '\0' '\n' < /proc/device-tree/compatible | grep -qx apple,j514s ||
        die 'The packaged M3 kernel is qualified on the 14-inch M3 Pro (J514s).'
    m3=1
    [[ -f /etc/default/limine && -f /var/lib/omarchy/limine.enabled ]] ||
        die 'This M3 installation needs the normal Omarchy Limine boot setup.'
fi
if (( check_only )); then
    echo 'Hardware and repository checks passed.'
    exit 0
fi
(( EUID == 0 )) || die 'Run the bootstrap as your normal user; it invokes sudo for installation.'
install -d -m700 /run/mac-steam-ultimate /run/mac-steam-native
exec 9>/run/mac-steam-ultimate/installer.lock
flock -n 9 || die 'Another Steam Ultimate installation is running.'
exec 8>/run/mac-steam-native/session.lock
flock -n 8 || die 'Close native Steam and its games, then rerun this installer.'
if pgrep -u "$uid" -f '^([^ ]*/)?muvm([[:space:]]|$)' >/dev/null || pgrep -u "$uid" -x steam >/dev/null; then
    die 'Close Steam and other muvm applications, then rerun this installer so they can use the new drivers.'
fi
[[ $(df --output=avail -k /opt | tail -1) -gt 6291456 ]] || die 'At least 6 GiB of free disk space is required.'
# Use the native ARM Steam package explicitly: asahi-alarm/steam is the older x86 wrapper.
# Keep Omarchy's update policy and use a package cache for missing ARM mirror files.
# shellcheck source=../common/pacman-install.sh
source "$project/../common/pacman-install.sh"
mac_install_packages omarchy/steam muvm FEX-Emu fex-emu-rootfs-arch \
    mesa-fex-emu-overlay-x86_64 mesa-fex-emu-overlay-i386 omarchy-steam-fex \
    erofs-utils python curl zstd vulkan-tools gamemode polkit
# Use the package's narrowly scoped Polkit rule for temporary CPU governor requests.
# Polkit sees this membership immediately; no password prompt or new login is needed.
usermod -aG gamemode "$target_user"
mkdir -p "$cache" /opt/mac-steam-ultimate/releases
while read -r hash file; do
    [[ $file && $hash ]] || continue
    [[ $file != linux-aurora-dsc-* || $m3 == 1 ]] || continue
    if ! printf '%s  %s\n' "$hash" "$cache/$file" | sha256sum --check --status 2>/dev/null; then
        asset_base=$base
        case $file in fex-aoe2-b608a4767-r2-*|userpages-*) asset_base=$native_base ;; esac
        curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$asset_base/$file" -o "$cache/$file.part"
        printf '%s  %s\n' "$hash" "$cache/$file.part" | sha256sum --check --status || die "Checksum mismatch: $file"
        mv "$cache/$file.part" "$cache/$file"
    fi
done < "$project/artifacts.sha256"
stage=$(mktemp -d /opt/mac-steam-ultimate/releases/.install-XXXXXX)
prior_current=$(readlink -f /opt/mac-steam-ultimate/current || :)
activated=0
cleanup() {
    result=$?
    rm -rf -- "$stage"
    if (( result != 0 && activated )); then
        if [[ -n $prior_current ]]; then
            ln -sfn "$prior_current" /opt/mac-steam-ultimate/current.recover
            mv -Tf /opt/mac-steam-ultimate/current.recover /opt/mac-steam-ultimate/current
        else
            rm -f /opt/mac-steam-ultimate/current
        fi
        echo 'Installation failed; restored the previous active version.' >&2
    fi
    exit "$result"
}
trap cleanup EXIT
chmod 755 "$stage"
mkdir -p "$stage/fex" "$stage/mesa-aarch64" "$stage/runtime" "$stage/wine-focus" "$stage/userpages"
tar --zstd -xf "$cache/fex-aoe2-b608a4767-r2-aarch64.tar.zst" -C "$stage/fex"
tar --zstd -xf "$cache/userpages-3bdf11d3-r1-aarch64.tar.zst" -C "$stage/userpages"
tar --zstd -xf "$cache/mesa-672657e-r1-aarch64.tar.zst" -C "$stage/mesa-aarch64"
mkdir -p "$stage/sources/mesa"
tar --zstd -xf "$cache/mesa-672657e-r1-source.tar.zst" -C "$stage/sources/mesa"
mkdir -p "$stage/x86-stage"
tar --zstd -xf "$cache/mesa-672657e-r1-x86.tar.zst" -C "$stage/x86-stage"
tar --zstd -xf "$cache/wine-focus-7b3ceaf-r1-x86_64.tar.zst" -C "$stage/wine-focus"
mkdir -p "$stage/sources/wine-focus"
tar --zstd -xf "$cache/wine-focus-7b3ceaf-r1-source.tar.zst" -C "$stage/sources/wine-focus"
if (( m3 )); then
    mkdir -p "$stage/sources/kernel"
    cp "$cache/linux-aurora-dsc-7.2.11.aurora11-3.1-source.tar.zst" "$stage/sources/kernel/"
fi
bash "$project/build/overlays.sh" "$stage/x86-stage" "$stage/overlays" > "$cache/overlays.log" 2>&1
rm -rf "$stage/x86-stage"
cp -a "$project/runtime/." "$stage/runtime/"
chmod 755 "$stage/runtime/"*
cp "$project/artifacts.sha256" "$stage/"
# A normal-user bootstrap owns its checkout; installed system files belong to root.
chown -R root:root "$stage"
for library in libvulkan_asahi.so libgallium-26.3.0-devel.so libEGL_mesa.so.0 libGLX_mesa.so.0 libgbm.so.1 dri/libdril_dri.so gbm/dri_gbm.so; do
    [[ -f /usr/lib/$library ]] || die "System Mesa layout has changed: /usr/lib/$library"
done
if ldd "$stage/mesa-aarch64/usr/lib/libvulkan_asahi.so" | grep -q 'not found'; then
    die 'Private Mesa has an unresolved system dependency.'
fi
if (( m3 )); then
    python3 "$stage/runtime/host-setup.py" tune
    package=$cache/linux-aurora-dsc-7.2.11.aurora11-3.1-aarch64.pkg.tar.zst
    module=/usr/lib/modules/7.2.11-11-dsc3-ARCH/kernel/drivers/gpu/drm/apple/appledrm.ko
    module_sha=9029fe79689441fb0ee9ddce60dc6f74903b5fb9f95c58fc8dbe4d4ea24c2328
    # Reinstall a modified same-version package too; --needed would skip repair.
    if [[ $(pacman -Q linux-aurora-dsc 2>/dev/null || :) != 'linux-aurora-dsc 7.2.11.aurora11-3.1' ]] ||
            ! printf '%s  %s\n' "$module_sha" "$module" | sha256sum --check --status 2>/dev/null; then
        pacman -U --noconfirm "$package"
    fi
    systemctl daemon-reload
    systemctl enable mac-steam-m3-panel.service
fi
boot_kernel=$(uname -r)
if (( m3 )); then boot_kernel=7.2.11-11-dsc3-ARCH; fi
python3 "$stage/runtime/boot-pages.py" --kernel "$boot_kernel"
if (( m3 )); then
    python3 "$stage/runtime/host-setup.py" select-kernel
fi

# Expose muvm's merged rootfs at Valve's graphics-provider discovery path.
mkdir -p /usr/share/guestos
if [[ -e /usr/share/guestos/fex-mesa && ! -L /usr/share/guestos/fex-mesa ]]; then
    die '/usr/share/guestos/fex-mesa already exists and is not a symlink.'
fi
ln -sfn /run/fex-emu/rootfs /usr/share/guestos/fex-mesa
installed=/opt/mac-steam-ultimate/releases/$release-$(date +%Y%m%dT%H%M%S)-$$
mv "$stage" "$installed"
if [[ -L /opt/mac-steam-ultimate/current ]]; then
    ln -sfn "$(readlink -f /opt/mac-steam-ultimate/current)" /opt/mac-steam-ultimate/previous
fi
ln -sfn "$installed" /opt/mac-steam-ultimate/current.new
mv -Tf /opt/mac-steam-ultimate/current.new /opt/mac-steam-ultimate/current
activated=1
install -d /usr/local/bin
install -d /usr/local/libexec /etc/polkit-1/rules.d
# pkexec canonicalizes executable symlinks before consulting its policy. Keep
# this entry point a regular file so its narrowly scoped rule has a stable path.
rm -f /usr/local/libexec/mac-steam-native
install -m755 "$installed/runtime/native-steam" /usr/local/libexec/mac-steam-native
# Authorize only this root-owned mount helper for the installed desktop account.
# It prepares fixed mounts and drops privileges before running any user code.
python3 - "$target_user" <<'PY'
import json
from pathlib import Path
import sys
account = json.dumps(sys.argv[1])
rule = '''polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.policykit.exec" &&
        action.lookup("program") == "/usr/local/libexec/mac-steam-native" &&
        subject.user == ACCOUNT && subject.local && subject.active) {
        return polkit.Result.YES;
    }
});
'''.replace('ACCOUNT', account)
path = Path('/etc/polkit-1/rules.d/49-mac-steam-native.rules')
path.write_text(rule)
path.chmod(0o644)
PY
ln -sfn /opt/mac-steam-ultimate/current/runtime/steam-mac-ultimate /usr/local/bin/steam-mac-ultimate
for name in steam omarchy-launch-steam; do
    destination=/usr/local/bin/$name
    if [[ -e $destination || -L $destination ]]; then
        [[ ! -d $destination ]] || die "Cannot replace directory: $destination"
        [[ -e $destination.pre-ultimate || -L $destination.pre-ultimate ]] ||
            cp -a "$destination" "$destination.pre-ultimate"
        rm -f "$destination"
    fi
    ln -s /opt/mac-steam-ultimate/current/runtime/steam-host "$destination"
done
runuser -u "$target_user" -- python3 /opt/mac-steam-ultimate/current/runtime/prepare.py
applications=$user_home/.local/share/applications
install -d -o "$target_user" -g "$(id -gn "$target_user")" "$applications"
desktop=$applications/steam.desktop
if [[ -e $desktop || -L $desktop ]]; then
    [[ -e $desktop.pre-ultimate || -L $desktop.pre-ultimate ]] || cp -a "$desktop" "$desktop.pre-ultimate"
    rm -f "$desktop"
fi
cat > "$desktop" <<'EOF'
[Desktop Entry]
Name=Steam (Mac Ultimate WIP)
Comment=Native ARM Steam with the AoE2-tested FEX and Apple Silicon graphics fixes
Exec=/usr/local/bin/steam-mac-ultimate %U
Icon=steam
Terminal=false
Type=Application
Categories=Network;Game;
MimeType=x-scheme-handler/steam;x-scheme-handler/steamlink;
StartupWMClass=Steam
EOF
chown "$target_user:$(id -gn "$target_user")" "$desktop"
runuser -u "$target_user" -- update-desktop-database "$applications" || :
runuser -u "$target_user" -- xdg-mime default steam.desktop x-scheme-handler/steam x-scheme-handler/steamlink || :
echo 'Installed! Open Steam (Mac Ultimate WIP) from your app launcher, or run steam-mac-ultimate.'
echo 'Sign in normally, install AoE2 DE, and use Proton Experimental. Steam supplies its own FEX tool and Vulkan bridge.'
echo 'The launcher applies the pinned AoE2 fixes when that tool finishes downloading.'
echo "Enable V-Sync in AoE2's advanced Graphics options for the tested responsive-cursor setup."
echo 'The native M3 comparison reached the intro in about 26 seconds; first use still downloads runtimes and installs prerequisites.'
echo 'GameMode requests the performance CPU governor while Steam runs and restores the previous setting when Steam closes.'
echo 'Mixed-page kernels get user4k=on and rebuilt, verified boot images. Reboot once to activate it.'
echo 'The tested M3 uses native FEX when 4 KB process support is active; --muvm keeps the VM path available.'
if (( m3 )); then
    echo 'Reboot once before playing: the qualified M3 display kernel is selected automatically.'
fi
echo "Installer log: $cache/overlays.log"
