#!/usr/bin/env bash
# Rebuild the pinned M3 kernel. Does not install packages or change boot files.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")" && pwd)
work=${1:-$HOME/.cache/mac-steam-kernel-build}
(( EUID != 0 )) || { echo 'Build the kernel as a regular user.' >&2; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo 'Requires an ARM64 build host.' >&2; exit 1; }
mkdir -p "$work"
cp -a "$project/kernel/." "$work/"
cd "$work"
exec makepkg --syncdeps --noconfirm
