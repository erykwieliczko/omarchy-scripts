#!/usr/bin/env bash
# Build the private FEX fork and source patchset without replacing distribution packages.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-/var/lib/mac-steam-ultimate}
commit=b608a47670de0ce6cca519858c2e57a2590344da
mkdir -p "$work"
if [[ ! -d $work/FEX/.git ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/StonkGuy/FEX.git "$work/FEX"
fi
[[ $(git -C "$work/FEX" rev-parse HEAD 2>/dev/null || :) == "$commit" ]] ||
    git -C "$work/FEX" checkout --detach "$commit"
# BUILD_TESTING=OFF does not need the large precompiled test collections.
git -C "$work/FEX" submodule update --init --recursive --depth 1 --jobs 4 -- \
    External/vixl Source/Common/cpp-optparse External/fmt External/drm-headers \
    External/xxhash External/Catch2 External/Vulkan-Headers External/jemalloc_glibc \
    External/tracy External/range-v3 External/zydis External/unordered_dense External/rpmalloc
patches=("$project"/patches/fex/000{2,3,4,6}-*.patch)
for patch in "${patches[@]}"; do
    if ! git -C "$work/FEX" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$work/FEX" apply --check "$patch"
        git -C "$work/FEX" apply "$patch"
    fi
done
cmake -S "$work/FEX" -B "$work/fex-build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DENABLE_ASSERTIONS=OFF \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_DISABLE_FIND_PACKAGE_fmt=TRUE \
    -DCMAKE_DISABLE_FIND_PACKAGE_xxhash=TRUE -DBUILD_STEAM_SUPPORT=TRUE
cmake --build "$work/fex-build" --parallel "${JOBS:-10}"
mkdir -p "$work/fex-stage/bin" "$work/fex-stage/licenses" "$work/fex-stage/patches/fex"
for name in FEX FEXBash FEXGetConfig FEXServer FEXServerManager FEXCompatTool; do
    [[ ! -f $work/fex-build/Bin/$name ]] ||
        install -m755 "$work/fex-build/Bin/$name" "$work/fex-stage/bin/$name"
done
cp "$work/FEX/LICENSE" "$work/fex-stage/licenses/FEX.txt"
# Preserve bundled dependency license notices as well.
find "$work/FEX/External" -type f \( -iname 'license*' -o -iname 'copying*' \) -print0 |
    while IFS= read -r -d '' file; do
        name=${file#"$work/FEX/"}
        mkdir -p "$work/fex-stage/licenses/$(dirname "$name")"
        cp "$file" "$work/fex-stage/licenses/$name"
    done
# Keep original patch mail headers/messages in the binary archive for attribution.
cp "${patches[@]}" "$work/fex-stage/patches/fex/"
{
    printf '%s\n' "$commit + patches/fex/0002,0003,0004,0006"
    printf '%s\n' 'PR 6081: https://github.com/FEX-Emu/FEX/pull/6081'
    printf '%s\n' 'Upstream commit: 61663da5bc8391130e4d3fdf0797f0ff9fe44161'
    printf '%s\n' 'Author: jgoyvaerts <1125884+jgoyvaerts@users.noreply.github.com>'
} > "$work/fex-stage/SOURCE.txt"
tar --zstd -cf "$work/fex-aoe2-b608a4767-r2-aarch64.tar.zst" -C "$work/fex-stage" .
