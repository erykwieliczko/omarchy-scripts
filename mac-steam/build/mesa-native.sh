#!/usr/bin/env bash
# Build a private ARM64 Steam graphics stack. This does not install it.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-"$HOME/.cache/mac-steam-build"}
commit=672657e05e6b382a0203975f7a26c46f9a674973
mkdir -p "$work"
if [[ ! -d $work/mesa/.git ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/omacom/mesa.git "$work/mesa"
    git -C "$work/mesa" checkout --detach "$commit"
fi
[[ $(git -C "$work/mesa" rev-parse HEAD) == "$commit" ]]
for patch in "$project"/patches/mesa/*.patch; do
    if ! git -C "$work/mesa" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$work/mesa" apply --check "$patch"
        git -C "$work/mesa" apply "$patch"
    fi
done
common=(--buildtype release --wrap-mode nodownload -Db_ndebug=true '-Dplatforms=x11,wayland'
    -Dgallium-drivers=asahi -Dvulkan-drivers=asahi -Degl=enabled -Dgbm=enabled
    -Dglx=dri -Dglvnd=enabled -Dgles1=disabled -Dgles2=enabled -Dvideo-codecs=
    -Dvulkan-layers= -Dlmsensors=disabled -Dlibunwind=disabled -Dvalgrind=disabled
    -Dbuild-tests=false)
[[ -d $work/mesa-tools ]] || meson setup "$work/mesa-tools" "$work/mesa" \
    --prefix /usr "${common[@]}" -Dllvm=enabled
ninja -C "$work/mesa-tools" -j "${JOBS:-8}" \
    src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc
cat > "$work/native-tools.ini" <<EOF
[binaries]
mesa_clc = '$work/mesa-tools/src/compiler/clc/mesa_clc'
vtn_bindgen2 = '$work/mesa-tools/src/compiler/spirv/vtn_bindgen2'
asahi_clc = '$work/mesa-tools/src/asahi/clc/asahi_clc'
EOF
[[ -d $work/mesa-build ]] || meson setup "$work/mesa-build" "$work/mesa" \
    --prefix /usr --libdir lib "${common[@]}" --native-file "$work/native-tools.ini" \
    -Dllvm=disabled -Dmesa-clc=system -Dprecomp-compiler=system -Dspirv-tools=disabled
ninja -C "$work/mesa-build" -j "${JOBS:-8}"
DESTDIR="$work/mesa-stage" meson install -C "$work/mesa-build" --no-rebuild
mkdir -p "$work/mesa-stage/usr/share/licenses/mac-steam-mesa"
cp "$work/mesa/docs/license.rst" "$work/mesa-stage/usr/share/licenses/mac-steam-mesa/"
printf '%s\n' "$commit + patches/mesa/0001 through 0005" > "$work/mesa-stage/SOURCE.txt"
tar --zstd -cf "$work/mesa-672657e-r1-aarch64.tar.zst" -C "$work/mesa-stage" .
