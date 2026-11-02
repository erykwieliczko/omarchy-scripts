#!/usr/bin/env bash
# Install against Omarchy's repositories with a package-only ARM mirror fallback.
mac_install_packages() (
    set -euo pipefail
    local temporary
    temporary=$(mktemp -d)
    trap 'rm -rf -- "$temporary"' EXIT
    # pacman-conf expands Includes while retaining repository order and policy.
    # CacheServer never supplies databases. Pacman still checks package hashes
    # and signatures against the selected Omarchy repository's metadata.
    pacman-conf | awk '
        /^\[/ {
            repository = $0
            eligible = repository == "[core]" || repository == "[extra]" ||
                       repository == "[alarm]" || repository == "[aur]"
        }
        {
            print
            if (eligible && $0 ~ /^Server = https:\/\/arm(-rc|-stable)?-mirror\.omarchy\.org\//) {
                print "CacheServer = https://de3.mirror.archlinuxarm.org/$arch/$repo"
                eligible = 0
            }
        }
    ' > "$temporary/pacman.conf"
    # Omarchy owns repository refreshes and full upgrades through its updater.
    pacman --config "$temporary/pacman.conf" -S --needed --noconfirm "$@"
)
