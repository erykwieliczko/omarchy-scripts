#!/usr/bin/env bash
# Install Mac Steam Ultimate WIP — M3 Pro / Omarchy Apple Silicon.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")" && pwd)
release=mac-steam-ultimate-wip-v0.1.0
base=https://github.com/erykwieliczko/omarchy-scripts/releases/download/$release
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
                'Requires Omarchy/Arch ARM on the qualified Apple M3 Pro (T6030).' \
                'Run from your desktop account with sudo, or specify --user as root.'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
die() { echo "Steam Ultimate: $*" >&2; exit 1; }
[[ $(uname -m) == aarch64 ]] || die 'This installer requires an ARM64 Mac running Linux.'
[[ -f /etc/arch-release ]] || die 'This installer requires Omarchy/Arch Linux ARM.'
[[ -r /proc/device-tree/compatible ]] || die 'Cannot identify the Apple Silicon hardware.'
tr '\0' '\n' < /proc/device-tree/compatible | grep -qx 'apple,t6030' ||
    die 'This WIP release is qualified for M3 Pro (T6030) only.'
[[ $(getconf PAGESIZE) == 16384 ]] || die 'Expected the qualified 16K host kernel.'
for repo in omarchy asahi-alarm; do
    pacman-conf --repo-list | grep -qx "$repo" || die "Required pacman repository is missing: $repo"
done
if [[ -z $target_user && $EUID != 0 ]]; then target_user=$(id -un); fi
if [[ -z $target_user ]]; then
    target_user=$(loginctl list-sessions --no-legend | awk '$4 == "seat0" && $3 != "root" { print $3; exit }')
fi
[[ -n $target_user && $target_user != root ]] || die 'Use --user YOUR_DESKTOP_ACCOUNT.'
uid=$(id -u "$target_user")
(( uid >= 1000 )) || die 'The target must be a regular desktop account.'
user_home=$(getent passwd "$target_user" | cut -d: -f6)
[[ -d $user_home && $user_home == /* ]] || die 'The desktop home directory does not exist.'
printf 'Target: %s (%s), kernel %s\n' "$target_user" "$user_home" "$(uname -r)"
if (( check_only )); then
    echo 'Hardware and repository checks passed.'
    exit 0
fi
(( EUID == 0 )) || die 'Run the bootstrap as your normal user; it invokes sudo for installation.'
exec 9>/run/lock/mac-steam-ultimate.lock
flock -n 9 || die 'Another Steam Ultimate installation is running.'
if pgrep -u "$uid" -x muvm >/dev/null; then
    die 'Close Steam and other muvm applications, then rerun this installer so the VM can use the new drivers.'
fi
[[ $(df --output=avail -k /opt | tail -1) -gt 6291456 ]] || die 'At least 6 GiB of free disk space is required.'
# Use the native ARM Steam package explicitly: asahi-alarm/steam is the older x86 wrapper.
# Never refresh databases without the corresponding full upgrade.
pacman -S --needed --noconfirm omarchy/steam muvm FEX-Emu fex-emu-rootfs-arch \
    mesa-fex-emu-overlay-x86_64 mesa-fex-emu-overlay-i386 omarchy-steam-fex \
    erofs-utils python curl zstd vulkan-tools
mkdir -p "$cache" /opt/mac-steam-ultimate/releases
while read -r hash file; do
    [[ $file && $hash ]] || continue
    if ! printf '%s  %s\n' "$hash" "$cache/$file" | sha256sum --check --status 2>/dev/null; then
        curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$base/$file" -o "$cache/$file.part"
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
mkdir -p "$stage/fex" "$stage/mesa-aarch64" "$stage/runtime"
tar --zstd -xf "$cache/fex-aoe2-b608a4767-r1-aarch64.tar.zst" -C "$stage/fex"
tar --zstd -xf "$cache/mesa-672657e-r1-aarch64.tar.zst" -C "$stage/mesa-aarch64"
mkdir -p "$stage/sources/mesa"
tar --zstd -xf "$cache/mesa-672657e-r1-source.tar.zst" -C "$stage/sources/mesa"
mkdir -p "$stage/x86-stage"
tar --zstd -xf "$cache/mesa-672657e-r1-x86.tar.zst" -C "$stage/x86-stage"
bash "$project/build/overlays.sh" "$stage/x86-stage" "$stage/overlays" > "$cache/overlays.log" 2>&1
rm -rf "$stage/x86-stage"
cp -a "$project/runtime/." "$stage/runtime/"
chmod 755 "$stage/runtime/"*
cp "$project/artifacts.sha256" "$stage/"
for library in libvulkan_asahi.so libgallium-26.3.0-devel.so libEGL_mesa.so.0 libGLX_mesa.so.0 libgbm.so.1 dri/libdril_dri.so gbm/dri_gbm.so; do
    [[ -f /usr/lib/$library ]] || die "System Mesa layout has changed: /usr/lib/$library"
done
if ldd "$stage/mesa-aarch64/usr/lib/libvulkan_asahi.so" | grep -q 'not found'; then
    die 'Private Mesa has an unresolved system dependency.'
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
Comment=Native ARM Steam with the AoE2-tested FEX and M3 Pro graphics fixes
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
echo "Installer log: $cache/overlays.log"
