#!/usr/bin/env bash
# Install Mac Steam Ultimate WIP
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -

main() {
    set -euo pipefail
    case ${1:-} in
        --help|-h)
            printf '%s\n' 'Install Mac Steam Ultimate WIP' \
                'Usage: bash install-mac-steam-ultimate-wip.sh [--check] [--user DESKTOP_ACCOUNT]' \
                'For Omarchy/Arch ARM with Apple Silicon graphics packages.' \
                'Run from your normal desktop account; installation invokes sudo.'
            return 0 ;;
    esac
    if [[ $(uname -m) != aarch64 || ! -f /etc/arch-release ]]; then
        echo 'Install Mac Steam Ultimate WIP requires Omarchy/Arch Linux ARM on Apple Silicon.' >&2
        return 1
    fi
    revision=7a73191d94df09f9af9ce42e2113c5e0009646e7
    archive_sha256=b7bb13e647f01764e8625acc05c8c66c4dcafc8192a0432a2b07731b2fac16be
    bootstrap_dir=$(mktemp -d)
    trap 'rm -rf -- "$bootstrap_dir"' EXIT
    echo 'Downloading Install Mac Steam Ultimate WIP (pinned installer)...'
    curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
        "https://codeload.github.com/erykwieliczko/omarchy-scripts/tar.gz/$revision" \
        -o "$bootstrap_dir/installer.tar.gz"
    printf '%s  %s\n' "$archive_sha256" "$bootstrap_dir/installer.tar.gz" | sha256sum --check --status || {
        echo 'Installer archive checksum failed.' >&2
        return 1
    }
    mkdir "$bootstrap_dir/repo"
    tar -xzf "$bootstrap_dir/installer.tar.gz" --strip-components=1 \
        --no-same-owner --no-same-permissions -C "$bootstrap_dir/repo"
    if (( EUID == 0 )); then
        bash "$bootstrap_dir/repo/mac-steam/install.sh" "$@"
    elif [[ " $* " == *' --check '* ]]; then
        bash "$bootstrap_dir/repo/mac-steam/install.sh" --user "$(id -un)" "$@"
    else
        echo 'Installing system dependencies and the pinned Steam/FEX graphics stack (sudo)...'
        sudo -- bash "$bootstrap_dir/repo/mac-steam/install.sh" --user "$(id -un)" "$@"
    fi
}

# Bash reads this whole function before invoking commands that might use stdin.
main "$@"
