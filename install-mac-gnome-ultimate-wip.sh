#!/usr/bin/env bash
# Install Mac GNOME Ultimate WIP
# curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-gnome-ultimate-wip.sh | bash -

main() {
    set -euo pipefail
    case ${1:-} in
        --help|-h)
            printf '%s\n' 'Install Mac GNOME Ultimate WIP' \
                'Usage: bash install-mac-gnome-ultimate-wip.sh [--check] [--user ACCOUNT] [--activate]' \
                'Installs full GNOME, Fedora-inspired defaults, apps, Flathub and GDM password login.' \
                '--activate closes the current graphical session after installation.'
            return 0 ;;
    esac
    if [[ ! -f /etc/arch-release ]]; then
        echo 'Install Mac GNOME Ultimate WIP requires Omarchy/Arch Linux.' >&2
        return 1
    fi
    revision=6d61e025aa3205ac5ba762769fc640288c23b546
    archive_sha256=204c6e9db80cc8eb8ddf7b55ae4b4cc69113fb16d2366794dce85fdc237a95b8
    bootstrap_dir=$(mktemp -d)
    trap 'rm -rf -- "$bootstrap_dir"' EXIT
    echo 'Downloading Install Mac GNOME Ultimate WIP (pinned installer)...'
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
        bash "$bootstrap_dir/repo/gnome/install.sh" "$@"
    elif [[ " $* " == *' --check '* ]]; then
        bash "$bootstrap_dir/repo/gnome/install.sh" --user "$(id -un)" "$@"
    else
        echo 'Installing GNOME and configuring GDM password login (sudo)...'
        sudo -- bash "$bootstrap_dir/repo/gnome/install.sh" --user "$(id -un)" "$@"
    fi
}

# Read the complete function before sudo or package tools can use stdin.
main "$@"
