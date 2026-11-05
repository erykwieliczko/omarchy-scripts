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
    if [[ ! -f /etc/arch-release ]]; then
        echo 'Install Mac KDE Ultimate WIP requires Omarchy/Arch Linux.' >&2
        return 1
    fi
    revision=1013819a4eadb74bda81b6a72e72144def15759e
    archive_sha256=3b792304a14e353b8ce22aec84de0724cc2376cae391a35f13d0ba53cf649853
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
