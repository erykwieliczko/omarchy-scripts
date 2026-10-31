#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
stage=${1:?Usage: overlays.sh X86_STAGE_PARENT OUTPUT_DIRECTORY}
out=${2:?Usage: overlays.sh X86_STAGE_PARENT OUTPUT_DIRECTORY}
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$out"
for arch in x86_64 i386; do
    lib=lib
    [[ $arch != i386 ]] || lib=lib32
    tree=$work/$arch
    fsck.erofs --extract="$tree" "/usr/share/fex-emu/overlays/mesa-$arch.erofs"
    dest=$tree/usr/$lib
    source=$stage/stage-$arch/usr
    rm -f "$dest"/libgallium-*.so "$dest"/libEGL_mesa.so* "$dest"/libGLX_mesa.so* \
        "$dest"/libgbm.so* "$dest/libvulkan_asahi.so" "$dest/gbm/dri_gbm.so" \
        "$dest/ovl_dri/libdril_dri.so" "$dest"/libRusticlOpenCL.so*
    rm -rf "$tree/etc/OpenCL"
    cp -a "$source/$lib"/libgallium-*.so "$source/$lib"/libEGL_mesa.so* \
        "$source/$lib"/libGLX_mesa.so* "$source/$lib"/libgbm.so* \
        "$source/$lib/libvulkan_asahi.so" "$dest/"
    cp -a "$source/$lib/gbm/dri_gbm.so" "$dest/gbm/"
    cp -a "$source/$lib/dri/libdril_dri.so" "$dest/ovl_dri/"
    cp -a "$source/share/drirc.d/." "$tree/usr/share/drirc.d/"
    cp -a "$source/share/vulkan/icd.d/." "$tree/usr/share/vulkan/ovl_icd.d/"
    cp -a "$source/share/glvnd/egl_vendor.d/." "$tree/usr/share/glvnd/ovl_egl_vendor.d/"
    ln -sfn libGLX_mesa.so.0 "$dest/libGLX_system.so.0"
    mkdir -p "$tree/usr/share/licenses/mac-steam-mesa"
    cp -a "$source/share/licenses/mac-steam-mesa/." "$tree/usr/share/licenses/mac-steam-mesa/"
    if [[ $arch == x86_64 ]]; then
        cp "$project/config/graphics_provider.json" "$tree/graphics_provider.json"
        # Arch's 32-bit overlay does not supply gconv; don't advertise it.
        python3 - "$tree/graphics_provider.json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data['graphics_provider_v0']['architectures']['i386-linux-gnu'].pop('gconv', None)
with open(path, 'w') as stream:
    json.dump(data, stream, indent=2)
    stream.write('\n')
PY
    fi
    mkfs.erofs -b 4096 -zlz4hc "$out/mesa-$arch.erofs.new" "$tree"
    mv "$out/mesa-$arch.erofs.new" "$out/mesa-$arch.erofs"
done
