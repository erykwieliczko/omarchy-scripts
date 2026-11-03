#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-"$HOME/.cache/mac-steam-x86-build"}
[[ $(uname -m) == x86_64 ]]
mkdir -p "$work/out"
if [[ ! -d $work/mesa/.git ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/omacom/mesa.git "$work/mesa"
    git -C "$work/mesa" checkout --detach a19691114759e2c0507f3502cf6166ef2c6e2e33
fi
[[ $(git -C "$work/mesa" rev-parse HEAD) == a19691114759e2c0507f3502cf6166ef2c6e2e33 ]]
for patch in "$project"/patches/mesa/*.patch; do
    if ! git -C "$work/mesa" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$work/mesa" apply --check "$patch"
        git -C "$work/mesa" apply "$patch"
    fi
done
docker run --rm -v "$work/mesa:/src:ro" -v "$work/out:/out" \
    -v "$project/build/mesa-x86-container.sh:/build.sh:ro" archlinux:base-devel bash /build.sh
for arch in x86_64 i386; do
    {
        printf '%s\n' 'omacom/mesa a19691114759e2c0507f3502cf6166ef2c6e2e33 + patches/mesa/0001 through 0008'
        (cd "$project" && sha256sum patches/mesa/*.patch)
    } | docker run --rm -i -v "$work/out:/out" archlinux:base-devel \
        sh -c 'cat > "$1"' sh "/out/stage-$arch/SOURCE.txt"
done
tar --zstd -cf "$work/mesa-a196911-r2-x86.tar.zst" -C "$work/out" stage-x86_64 stage-i386
