#!/usr/bin/env bash
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -

main() {
    set -euo pipefail
    check_only=0
    while (( $# )); do
        case $1 in
            --check) check_only=1; shift ;;
            --help|-h)
                printf '%s\n' 'Set up a PC-style Apple keyboard on Omarchy' \
                    'Usage: bash setup-mac-keyboard.sh [--check]' \
                    'Swap Option/Command on both sides, swap Fn/left Ctrl, and use F1-F12 by default.' \
                    '--check verifies support and displays current settings without changing anything.'
                return 0 ;;
            *) echo "Unknown argument: $1" >&2; return 2 ;;
        esac
    done
    die() { echo "Mac keyboard: $*" >&2; exit 1; }
    [[ $(uname -m) == aarch64 && -f /etc/arch-release ]] ||
        die 'Requires Omarchy/Arch Linux ARM on Apple Silicon.'
    [[ -r /proc/device-tree/compatible ]] || die 'Cannot identify this Mac.'
    tr '\0' '\n' < /proc/device-tree/compatible | grep -qx 'apple,arm-platform' ||
        die 'Requires an Apple Silicon Mac.'
    [[ -x /usr/bin/omarchy ]] || die 'Omarchy must be installed first.'
    for tool in mkinitcpio modprobe flock; do
        command -v "$tool" >/dev/null || die "Required command is missing: $tool"
    done

    parameters=/sys/module/hid_apple/parameters
    names=(fnmode swap_opt_cmd swap_fn_leftctrl)
    values=(2 1 1)
    for name in "${names[@]}"; do
        [[ -r $parameters/$name ]] || die "The loaded Apple keyboard driver lacks $name."
    done
    printf 'Apple keyboard support verified. Current settings:\n'
    for name in "${names[@]}"; do
        printf '  %s=%s\n' "$name" "$(<"$parameters/$name")"
    done
    (( check_only )) && return 0

    if (( EUID != 0 )); then
        echo 'Applying keyboard settings (sudo)...'
        # The full function is already read, so this also works when piped into bash.
        exec sudo -- bash -c "$(declare -f main); main \"\$@\"" bash "$@"
    fi
    exec 9>/run/lock/omarchy-mac-keyboard.lock
    flock -n 9 || die 'Another keyboard setup is running.'

    config=/etc/modprobe.d/apple-keyboard.conf
    [[ ! -L $config && ( ! -e $config || -f $config ) ]] ||
        die "$config must be a regular file, or absent."
    backup=/var/lib/omarchy-mac-keyboard/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$
    install -d -m700 "$backup"
    config_existed=0
    if [[ -f $config ]]; then
        cp -a -- "$config" "$backup/apple-keyboard.conf"
        config_existed=1
    fi
    for name in "${names[@]}"; do
        cat "$parameters/$name" > "$backup/before-$name"
    done
    shopt -s nullglob
    images=(/boot/initramfs-*.img)
    shopt -u nullglob
    (( ${#images[@]} )) || die 'No /boot/initramfs-*.img images found; nothing changed.'
    for image in "${images[@]}"; do
        cp -a --reflink=auto -- "$image" "$backup/"
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
            for name in "${names[@]}"; do
                cat "$backup/before-$name" > "$parameters/$name" || restore_failed=1
            done
            if (( rebuilding )); then
                for image in "${images[@]}"; do
                    cp -a --reflink=auto -- "$backup/${image##*/}" "$image" || restore_failed=1
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

    install -d -m755 /etc/modprobe.d
    temporary=$(mktemp /etc/modprobe.d/.apple-keyboard.XXXXXX)
    cat > "$temporary" <<'EOF'
# PC-style modifiers and F1-F12 by default on the Apple keyboard.
# Physical Fn -> left Ctrl; physical left Ctrl -> Fn.
# Option -> Super; Command -> Alt (right Command -> right Alt / AltGr).
options hid_apple fnmode=2 swap_opt_cmd=1 swap_fn_leftctrl=1
EOF
    chmod 644 "$temporary"
    changed=1
    mv -f -- "$temporary" "$config"
    temporary=

    # A later modprobe option must not silently undo a setting at the next boot.
    effective=$(modprobe -c | awk '
        $1 == "options" && ($2 == "hid_apple" || $2 == "hid-apple") {
            for (i = 3; i <= NF; i++) {
                split($i, option, "=")
                settings[option[1]] = option[2]
            }
        }
        END { print settings["fnmode"], settings["swap_opt_cmd"], settings["swap_fn_leftctrl"] }
    ')
    [[ $effective == '2 1 1' ]] ||
        die 'Other modprobe settings override this configuration; resolve the conflict and rerun.'

    echo "Backups: $backup"
    echo 'Rebuilding boot images with the saved keyboard settings...'
    rebuilding=1
    mkinitcpio -P 2>&1 | tee "$backup/mkinitcpio.log"
    for index in "${!names[@]}"; do
        printf '%s\n' "${values[$index]}" > "$parameters/${names[$index]}"
    done
    for index in "${!names[@]}"; do
        [[ $(<"$parameters/${names[$index]}") == "${values[$index]}" ]] ||
            die "Could not verify ${names[$index]}."
    done
    changed=0
    printf '%s\n' 'Keyboard settings applied and saved. No reboot needed.' \
        'Option = Super; Command = Alt (right Command = right Alt / AltGr).' \
        'Physical Fn = left Ctrl; physical left Ctrl = Fn.' \
        'F1-F12 work directly. Hold physical left Ctrl for volume/brightness/media controls.'
}

# Read the complete function before sudo or other commands can consume stdin.
main "$@"
