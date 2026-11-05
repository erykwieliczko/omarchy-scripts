#!/usr/bin/env bash
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -

main() {
    set -euo pipefail
    original_arguments=("$@")
    check_only=0
    right_option=super
    while (( $# )); do
        case $1 in
            --check) check_only=1; shift ;;
            --right-option=*) right_option=${1#*=}; shift ;;
            --right-option) right_option=${2:?--right-option needs super or ctrl}; shift 2 ;;
            --help|-h)
                printf '%s\n' 'Set up a PC-style Apple keyboard on Omarchy' \
                    'Usage: bash setup-mac-keyboard.sh [--right-option=super|ctrl] [--check]' \
                    'Swap Option/Command on both sides, swap Fn/left Ctrl, and use F1-F12 by default.' \
                    '--right-option=ctrl makes physical Right Option act as Right Ctrl instead of Super.' \
                    '--check verifies support and displays current settings without changing anything.'
                return 0 ;;
            *) echo "Unknown argument: $1" >&2; return 2 ;;
        esac
    done
    die() { echo "Mac keyboard: $*" >&2; exit 1; }
    right_option=${right_option,,}
    case $right_option in
        super) right_key=rightalt; right_code=100; right_label=Super ;;
        ctrl) right_key=rightctrl; right_code=97; right_label=Ctrl ;;
        *) die '--right-option must be super or ctrl.' ;;
    esac
    for tool in mkinitcpio modprobe flock python3 systemd-hwdb udevadm; do
        command -v "$tool" >/dev/null || die "Required command is missing: $tool"
    done

    parameters=/sys/module/hid_apple/parameters
    names=(fnmode swap_opt_cmd swap_fn_leftctrl)
    values=(2 1 1)
    extra_options=
    if [[ -r $parameters/swap_ctrl_cmd ]]; then
        names+=(swap_ctrl_cmd)
        values+=(0)
        extra_options=' swap_ctrl_cmd=0'
    fi
    for name in "${names[@]}"; do
        [[ -r $parameters/$name ]] || die "The loaded Apple keyboard driver lacks $name."
    done
    printf 'Apple keyboard support verified. Current settings:\n'
    for name in "${names[@]}"; do
        printf '  %s=%s\n' "$name" "$(<"$parameters/$name")"
    done
    printf 'Requested physical Right Option: %s\n' "$right_label"
    (( check_only )) && return 0

    if (( EUID != 0 )); then
        echo 'Applying keyboard settings (sudo)...'
        # The full function is already read, so this also works when piped into bash.
        exec sudo -- bash -c "$(declare -f main); main \"\$@\"" bash "${original_arguments[@]}"
    fi
    exec 9>/run/lock/omarchy-mac-keyboard.lock
    flock -n 9 || die 'Another keyboard setup is running.'

    config=/etc/modprobe.d/apple-keyboard.conf
    hwdb_config=/etc/udev/hwdb.d/90-omarchy-mac-keyboard.hwdb
    hwdb_binary=/etc/udev/hwdb.bin
    [[ ! -L $config && ( ! -e $config || -f $config ) ]] ||
        die "$config must be a regular file, or absent."
    [[ ! -L $hwdb_config && ( ! -e $hwdb_config || -f $hwdb_config ) ]] ||
        die "$hwdb_config must be a regular file, or absent."
    backup=/var/lib/omarchy-mac-keyboard/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$
    install -d -m700 "$backup"
    config_existed=0
    if [[ -f $config ]]; then
        cp -a -- "$config" "$backup/apple-keyboard.conf"
        config_existed=1
    fi
    hwdb_existed=0
    if [[ -f $hwdb_config ]]; then
        cp -a -- "$hwdb_config" "$backup/apple-keyboard.hwdb"
        hwdb_existed=1
    fi
    # Read only key-map metadata, never keystrokes. Restore the exact previous
    # live mapping if installation fails, including when no hwdb entry existed.
    right_option_keymap() {
        python3 - "$@" <<'PY'
import errno, fcntl, json, os, struct, sys
from pathlib import Path

def entry(keycode=0):
    return bytearray(struct.pack('=BBHI32s', 0, 4, 0, keycode, struct.pack('=I', 0x700e6)))

mode, argument = sys.argv[1:]
if mode == 'restore':
    devices = json.loads(Path(argument).read_text())
else:
    devices = []
    for device in sorted(Path('/sys/class/input').glob('event*')):
        vendor = device / 'device/id/vendor'
        if vendor.is_file() and vendor.read_text().strip().lower() == '05ac':
            devices.append({'device': '/dev/input/' + device.name,
                            'sysfs': str(device.resolve())})
snapshot = []
for device in devices:
    path = Path(device['device'])
    if not path.exists():
        continue
    if str((Path('/sys/class/input') / path.name).resolve()) != device['sysfs']:
        continue
    with path.open('rb', buffering=0) as handle:
        value = entry()
        try:
            fcntl.ioctl(handle, 0x80284504, value, True)  # EVIOCGKEYCODE_V2
        except OSError as error:
            if error.errno in (errno.EINVAL, errno.ENOTTY):
                continue  # An Apple trackpad or other non-keyboard interface.
            raise
        code = struct.unpack_from('=I', value, 4)[0]
        if mode == 'snapshot':
            snapshot.append(dict(device, keycode=code))
        elif mode == 'restore':
            fcntl.ioctl(handle, 0x40284504, entry(device['keycode']))  # EVIOCSKEYCODE_V2
        elif mode == 'verify' and code != int(argument):
            raise SystemExit(f'Right Option mapping did not apply to {path}: {code}')
if mode == 'snapshot':
    Path(argument).write_text(json.dumps(snapshot, indent=2) + '\n')
PY
    }
    right_option_keymap snapshot "$backup/before-keymap.json"
    for name in "${names[@]}"; do
        cat "$parameters/$name" > "$backup/before-$name"
    done
    shopt -s nullglob
    images=(/boot/initramfs-*.img)
    shopt -u nullglob
    (( ${#images[@]} )) || die 'No /boot/initramfs-*.img images found; nothing changed.'
    rebuild=(mkinitcpio -P)
    boot_files=("${images[@]}")
    esp=
    if [[ -f /var/lib/omarchy/limine.enabled && -f /etc/default/limine ]]; then
        for tool in limine-mkinitcpio python3 lsinitcpio; do
            command -v "$tool" >/dev/null || die "Required Limine command is missing: $tool"
        done
        esp=$(python3 - /etc/default/limine <<'PY'
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text()
match = re.search(r'''^ESP_PATH=["']?(/[^"'\n]*)["']?\s*$''', text, re.M)
if not match:
    raise SystemExit('Cannot identify the Limine ESP path')
print(match[1])
PY
        )
        [[ -f $esp/limine.conf ]] || die 'The active Limine configuration is missing.'
        shopt -s nullglob
        ukis=("$esp"/EFI/Linux/*.efi)
        shopt -u nullglob
        boot_files+=("$esp/limine.conf" "${ukis[@]}")
        rebuild=(limine-mkinitcpio)
    fi
    install -d -m700 "$backup/boot-files"
    printf '%s\0' "${boot_files[@]}" > "$backup/boot-files.list"
    for image in "${boot_files[@]}"; do
        cp -a --parents --reflink=auto -- "$image" "$backup/boot-files/"
    done

    changed=0
    rebuilding=0
    temporary=
    cleanup() {
        result=$?
        trap - EXIT
        if (( result != 0 && changed )); then
            echo 'Keyboard setup failed; restoring the previous settings and boot images.' >&2
            restore_failed=0
            if (( config_existed )); then
                cp -a -- "$backup/apple-keyboard.conf" "$config" || restore_failed=1
            else
                rm -f -- "$config" || restore_failed=1
            fi
            if (( hwdb_existed )); then
                cp -a -- "$backup/apple-keyboard.hwdb" "$hwdb_config" || restore_failed=1
            else
                rm -f -- "$hwdb_config" || restore_failed=1
            fi
            systemd-hwdb update || restore_failed=1
            for name in "${names[@]}"; do
                cat "$backup/before-$name" > "$parameters/$name" || restore_failed=1
            done
            right_option_keymap restore "$backup/before-keymap.json" || restore_failed=1
            if (( rebuilding )); then
                for image in "${boot_files[@]}"; do
                    cp -a --reflink=auto -- "$backup/boot-files$image" "$image" || restore_failed=1
                done
            fi
            if (( restore_failed )); then
                echo "Automatic restoration was incomplete. Backups: $backup" >&2
            else
                echo "Previous settings restored. Backups: $backup" >&2
            fi
        fi
        if [[ -n $temporary ]]; then rm -f -- "$temporary"; fi
        exit "$result"
    }
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    install -d -m755 /etc/modprobe.d /etc/udev/hwdb.d
    temporary=$(mktemp /etc/modprobe.d/.apple-keyboard.XXXXXX)
    cat > "$temporary" <<EOF
# PC-style modifiers and F1-F12 by default on the Apple keyboard.
# Physical Fn -> left Ctrl; physical left Ctrl -> Fn.
# Left Option -> Super; Right Option -> $right_label; Command -> Alt / AltGr.
options hid_apple fnmode=2 swap_opt_cmd=1 swap_fn_leftctrl=1$extra_options
EOF
    chmod 644 "$temporary"
    changed=1
    mv -f -- "$temporary" "$config"
    temporary=
    # Map the physical HID usage before hid_apple swaps Option/Command. A raw
    # Right Alt becomes Super with swap_opt_cmd=1; Right Ctrl remains Ctrl.
    temporary=$(mktemp /etc/udev/hwdb.d/.apple-keyboard.XXXXXX)
    cat > "$temporary" <<EOF
# Omarchy Apple keyboard: physical Right Option = $right_label.
evdev:input:b*v05ACp*
 KEYBOARD_KEY_700e6=$right_key
EOF
    chmod 644 "$temporary"
    mv -f -- "$temporary" "$hwdb_config"
    temporary=
    systemd-hwdb update

    # A later modprobe option must not silently undo a setting at the next boot.
    effective=$(modprobe -c | awk -v names="${names[*]}" '
        $1 == "options" && ($2 == "hid_apple" || $2 == "hid-apple") {
            for (i = 3; i <= NF; i++) {
                split($i, option, "=")
                settings[option[1]] = option[2]
            }
        }
        END {
            count = split(names, keys, " ")
            for (i = 1; i <= count; i++) printf "%s%s", i == 1 ? "" : " ", settings[keys[i]]
            print ""
        }
    ')
    [[ $effective == "${values[*]}" ]] ||
        die 'Other modprobe settings override this configuration; resolve the conflict and rerun.'

    echo "Backups: $backup"
    echo 'Rebuilding boot images with the saved keyboard settings...'
    rebuilding=1
    "${rebuild[@]}" 2>&1 | tee "$backup/mkinitcpio.log"
    if [[ -n $esp ]]; then
        # A successful raw initramfs build does not update a bootable UKI.
        # Verify the actual installed-kernel UKIs before accepting the change.
        python3 - "$config" "$esp" /etc/default/limine /etc/mkinitcpio.d /etc/machine-id "$hwdb_binary" <<'PY'
from pathlib import Path
import re, struct, subprocess, sys, tempfile
config, esp, defaults, presets, machine, hwdb = map(Path, sys.argv[1:])
text = defaults.read_text()
if re.search(r'''^ENABLE_UKI=["']?yes["']?\s*$''', text, re.M):
    match = re.search(r'''^CUSTOM_UKI_NAME=["']?([a-z0-9]+)["']?\s*$''', text, re.M)
    prefix = match[1] if match else machine.read_text().strip()
    kernels = sorted(presets.glob('*.preset'))
    if not kernels:
        raise SystemExit('No installed kernel presets to verify')
    for kernel in kernels:
        uki = esp / 'EFI/Linux' / f'{prefix}_{kernel.stem}.efi'
        data = uki.read_bytes()
        pe, = struct.unpack_from('<I', data, 0x3c)
        if data[pe:pe+4] != b'PE\0\0':
            raise SystemExit(f'Invalid UKI: {uki}')
        count, = struct.unpack_from('<H', data, pe+6)
        optional, = struct.unpack_from('<H', data, pe+20)
        initrd = None
        for index in range(count):
            section = pe+24+optional+40*index
            if data[section:section+8].rstrip(b'\0') == b'.initrd':
                size, _, _, offset = struct.unpack_from('<IIII', data, section+8)
                initrd = data[offset:offset+size]
                if len(initrd) != size:
                    raise SystemExit(f'Truncated UKI initrd: {uki}')
        if initrd is None:
            raise SystemExit(f'No initrd in UKI: {uki}')
        with tempfile.TemporaryDirectory(prefix='mac-keyboard-verify-') as directory:
            image = Path(directory) / 'initrd.img'
            image.write_bytes(initrd)
            subprocess.run(['lsinitcpio', '-x', str(image)], cwd=directory,
                           check=True, stdout=subprocess.DEVNULL)
            embedded = Path(directory) / 'etc/modprobe.d/apple-keyboard.conf'
            if not embedded.is_file() or embedded.read_bytes() != config.read_bytes():
                raise SystemExit(f'Keyboard configuration missing or stale in {uki}')
            database = Path(directory) / 'etc/udev/hwdb.bin'
            if not database.is_file() or database.read_bytes() != hwdb.read_bytes():
                raise SystemExit(f'Keyboard hardware database missing or stale in {uki}')
        print(f'Verified keyboard configuration in {uki.name}')
PY
    fi
    for index in "${!names[@]}"; do
        printf '%s\n' "${values[$index]}" > "$parameters/${names[$index]}"
    done
    for index in "${!names[@]}"; do
        [[ $(<"$parameters/${names[$index]}") == "${values[$index]}" ]] ||
            die "Could not verify ${names[$index]}."
    done
    udevadm trigger --action=change --subsystem-match=input
    udevadm settle
    right_option_keymap verify "$right_code"
    changed=0
    printf '%s\n' 'Keyboard settings applied and saved. No reboot needed.' \
        "Left Option = Super; Right Option = $right_label; Command = Alt (right Command = AltGr)." \
        'Physical Fn = left Ctrl; physical left Ctrl = Fn.' \
        'F1-F12 work directly. Hold physical left Ctrl for volume/brightness/media controls.'
}

# Read the complete function before sudo or other commands can consume stdin.
main "$@"
