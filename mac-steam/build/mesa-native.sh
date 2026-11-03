#!/usr/bin/env bash
# Build a private ARM64 Steam graphics stack. This does not install it.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-"$HOME/.cache/mac-steam-build"}
commit=a19691114759e2c0507f3502cf6166ef2c6e2e33
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
{
    printf '%s\n' "omacom/mesa $commit + patches/mesa/0001 through 0007"
    (cd "$project" && sha256sum patches/mesa/*.patch)
} > "$work/mesa-stage/SOURCE.txt"
tar --zstd -cf "$work/mesa-a196911-r1-aarch64.tar.zst" -C "$work/mesa-stage" .
cp "$work/mesa-stage/SOURCE.txt" "$work/mesa/SOURCE.txt"
tar --exclude=.git --zstd -cf "$work/mesa-a196911-r1-source.tar.zst" -C "$work/mesa" .
