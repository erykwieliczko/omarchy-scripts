#!/usr/bin/env bash
# Install Mac KDE Ultimate WIP
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -

main() {
    set -euo pipefail
    case ${1:-} in
        --help|-h)
            printf '%s\n' 'Install Mac KDE Ultimate WIP' \
                'Usage: bash install-mac-kde-ultimate-wip.sh [--check] [--user ACCOUNT] [--activate]' \
                'Installs native KDE Plasma and Plasma Login Manager with password login.' \
                '--activate closes the current graphical session after installation.'
            return 0 ;;
    esac
    if [[ $(uname -m) != aarch64 || ! -f /etc/arch-release ]]; then
        echo 'Install Mac KDE Ultimate WIP requires Omarchy/Arch Linux ARM on Apple Silicon.' >&2
        return 1
    fi
    revision=b819bb120d1ab43d8c27231e76e9fade726fc78e
    archive_sha256=5c0a31be06ab885762a4604806273bdbfca7a57c53a73cd2d87f23383fd78a9b
    bootstrap_dir=$(mktemp -d)
    trap 'rm -rf -- "$bootstrap_dir"' EXIT
    echo 'Downloading Install Mac KDE Ultimate WIP (pinned installer)...'
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
        bash "$bootstrap_dir/repo/kde/install.sh" "$@"
    elif [[ " $* " == *' --check '* ]]; then
        bash "$bootstrap_dir/repo/kde/install.sh" --user "$(id -un)" "$@"
    else
        echo 'Installing KDE Plasma and configuring password login (sudo)...'
        sudo -- bash "$bootstrap_dir/repo/kde/install.sh" --user "$(id -un)" "$@"
    fi
}

# Read the complete function before sudo or package tools can use stdin.
main "$@"
