#!/usr/bin/env bash
# Build the AoE2-tested FEX fork without replacing distribution packages.
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
git -C "$work/FEX" submodule update --init --recursive --depth 1
for patch in "$project"/patches/fex/*.patch; do
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
mkdir -p "$work/fex-stage/bin" "$work/fex-stage/licenses"
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
printf '%s\n' "$commit + patches/fex/0002,0003,0004" > "$work/fex-stage/SOURCE.txt"
tar --zstd -cf "$work/fex-aoe2-b608a4767-r1-aarch64.tar.zst" -C "$work/fex-stage" .
