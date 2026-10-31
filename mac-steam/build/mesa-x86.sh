#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-"$HOME/.cache/mac-steam-x86-build"}
[[ $(uname -m) == x86_64 ]]
mkdir -p "$work/out"
if [[ ! -d $work/mesa/.git ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/omacom/mesa.git "$work/mesa"
    git -C "$work/mesa" checkout --detach 672657e05e6b382a0203975f7a26c46f9a674973
fi
[[ $(git -C "$work/mesa" rev-parse HEAD) == 672657e05e6b382a0203975f7a26c46f9a674973 ]]
for patch in "$project"/patches/mesa/*.patch; do
    if ! git -C "$work/mesa" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$work/mesa" apply --check "$patch"
        git -C "$work/mesa" apply "$patch"
    fi
done
docker run --rm -v "$work/mesa:/src:ro" -v "$work/out:/out" \
    -v "$project/build/mesa-x86-container.sh:/build.sh:ro" archlinux:base-devel bash /build.sh
tar --zstd -cf "$work/mesa-672657e-r1-x86.tar.zst" -C "$work/out" stage-x86_64 stage-i386
