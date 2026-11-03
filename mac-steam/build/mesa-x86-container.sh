#!/bin/bash
# Runs inside archlinux:base-devel. /src = patched omacom/mesa, /out = results.
set -euo pipefail
grep -q '^\[multilib\]' /etc/pacman.conf || printf '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n' >> /etc/pacman.conf
pacman -Syu --noconfirm --needed meson ninja clang llvm libclc spirv-llvm-translator spirv-tools glslang \
  python-mako python-yaml python-packaging python-ply rust rust-bindgen \
  libdrm wayland wayland-protocols libx11 libxext libxfixes libxshmfence libxxf86vm libxrandr libxcb expat zstd zlib libglvnd \
  lib32-libdrm lib32-wayland lib32-libx11 lib32-libxext lib32-libxfixes lib32-libxshmfence lib32-libxxf86vm \
  lib32-libxrandr lib32-libxcb lib32-expat lib32-zstd lib32-zlib lib32-libglvnd lib32-gcc-libs >/dev/null
cd /src
common=(--buildtype release --wrap-mode nodownload -Db_ndebug=true '-Dplatforms=x11,wayland'
  -Dgallium-drivers=asahi -Dvulkan-drivers=asahi -Degl=enabled -Dgbm=enabled -Dglx=dri -Dglvnd=enabled
  -Dgles1=disabled -Dgles2=enabled -Dvideo-codecs= -Dvulkan-layers= -Dlmsensors=disabled -Dlibunwind=disabled
  -Dvalgrind=disabled -Dbuild-tests=false)
# Host tools (asahi_clc precompiles libagx; its output is the same for every CPU target).
[ -d /out/tools ] || meson setup /out/tools --prefix /usr "${common[@]}" -Dllvm=enabled
ninja -C /out/tools src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc
cat > /out/tools.ini <<TOOLS
[binaries]
mesa_clc = '/out/tools/src/compiler/clc/mesa_clc'
vtn_bindgen2 = '/out/tools/src/compiler/spirv/vtn_bindgen2'
asahi_clc = '/out/tools/src/asahi/clc/asahi_clc'
TOOLS
cat > /out/i686.ini <<'X'
[binaries]
c = ['gcc', '-m32']
cpp = ['g++', '-m32']
ar = 'ar'
strip = 'strip'
pkg-config = 'i686-pc-linux-gnu-pkg-config'
[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
X
printf '#!/bin/sh\nexport PKG_CONFIG_LIBDIR=/usr/lib32/pkgconfig:/usr/share/pkgconfig\nexec pkg-config "$@"\n' > /usr/local/bin/i686-pc-linux-gnu-pkg-config
chmod +x /usr/local/bin/i686-pc-linux-gnu-pkg-config
tgt=(--native-file /out/tools.ini -Dllvm=disabled -Dmesa-clc=system -Dprecomp-compiler=system -Dspirv-tools=disabled)
[ -d /out/x86_64 ] || meson setup /out/x86_64 --prefix /usr --libdir lib "${common[@]}" "${tgt[@]}"
[ -d /out/i386 ] || meson setup /out/i386 --prefix /usr --libdir lib32 --cross-file /out/i686.ini "${common[@]}" "${tgt[@]}"
for a in x86_64 i386; do
  ninja -C /out/$a
  rm -rf /out/stage-$a; DESTDIR=/out/stage-$a meson install -C /out/$a --no-rebuild >/dev/null
  mkdir -p /out/stage-$a/usr/share/licenses/mac-steam-mesa
  cp /src/docs/license.rst /out/stage-$a/usr/share/licenses/mac-steam-mesa/
done
echo X86_MESA_READY
