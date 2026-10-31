#!/usr/bin/env bash
# Install Mac Steam Ultimate WIP
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -

main() {
    set -euo pipefail
    case ${1:-} in
        --help|-h)
            printf '%s\n' 'Install Mac Steam Ultimate WIP' \
                'Usage: bash install-mac-steam-ultimate-wip.sh [--check] [--user DESKTOP_ACCOUNT]' \
                'For Omarchy/Arch ARM on Apple M1 (T8103) or M3 Pro (T6030).' \
                'Run from your normal desktop account; installation invokes sudo.'
            return 0 ;;
    esac
    if [[ $(uname -m) != aarch64 || ! -f /etc/arch-release ]]; then
        echo 'Install Mac Steam Ultimate WIP requires Omarchy/Arch Linux ARM on Apple Silicon.' >&2
        return 1
    fi
    revision=f604a186e0418a5bcb8c5d05b5f9122650841473
    archive_sha256=e40ad5a2d875c077e33f87738b105ce1d134097e016b7e353bade45e6133c6b6
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
