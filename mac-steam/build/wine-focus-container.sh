#!/usr/bin/env bash
set -euo pipefail
cd /src
./tools/make_requests
./tools/make_specfiles
python3 dlls/winevulkan/make_vulkan --xml vk.xml --video-xml video.xml
autoconf
autoheader
mkdir -p /build/objects
cd /build/objects
/src/configure --enable-win64 --without-mingw --without-wayland --disable-tests CFLAGS='-O2 -g' > configure.log 2>&1
# Build only this module; retain Valve's ntdll, win32u and all other modules.
make -j"$(nproc)" dlls/winex11.drv/winex11.so > build.log 2>&1
