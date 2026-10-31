#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${1:-"$HOME/.cache/mac-steam-wine-build"}
revision=7b3ceaf8644bb5d57140903e12897efac69be16a
[[ $(uname -m) == x86_64 ]]
mkdir -p "$work/out"
work=$(readlink -f "$work")
if [[ ! -d $work/wine/.git ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/ValveSoftware/wine.git "$work/wine"
    git -C "$work/wine" checkout --detach "$revision"
fi
[[ $(git -C "$work/wine" rev-parse HEAD) == "$revision" ]]
for patch in "$project"/patches/wine/*.patch; do
    if ! git -C "$work/wine" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$work/wine" apply --check "$patch"
        git -C "$work/wine" apply "$patch"
    fi
done
docker build -t mac-steam-wine-focus-builder -f "$project/build/wine-focus.Dockerfile" "$project/build"
docker run --rm --user "$(id -u):$(id -g)" -e XDG_CACHE_HOME=/build/cache \
    -v "$work/wine:/src" -v "$work/out:/build" \
    -v "$project/build/wine-focus-container.sh:/build.sh:ro" \
    mac-steam-wine-focus-builder bash /build.sh
mkdir -p "$work/out/binary"
cp "$work/out/objects/dlls/winex11.drv/winex11.so" "$work/out/binary/"
cp "$work/wine/COPYING.LIB" "$work/out/binary/"
python3 - "$project" "$work" <<'PY'
import hashlib, json
from pathlib import Path
import sys
project, work = map(Path, sys.argv[1:])
manifest = json.loads((project / 'build/wine-focus-manifest.json').read_text())
manifest['patched_sha256'] = hashlib.sha256((work / 'out/binary/winex11.so').read_bytes()).hexdigest()
(work / 'out/binary/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
tar --zstd -cf "$work/wine-focus-7b3ceaf-r1-x86_64.tar.zst" -C "$work/out/binary" .
# Full corresponding source, including the patch, build recipe and regression.
mkdir -p "$work/out/source/wine" "$work/out/source/build-support"
git -C "$work/wine" archive "$revision" | tar -xf - -C "$work/out/source/wine"
for patch in "$project"/patches/wine/*.patch; do
    (cd "$work/out/source/wine" && git apply "$patch")
done
cp "$project"/build/wine-focus* "$work/out/source/build-support/"
cp "$project/tests/focus-retry.py" "$work/out/source/build-support/"
cp "$project"/patches/wine/*.patch "$work/out/source/build-support/"
printf '%s\n' "$revision" > "$work/out/source/SOURCE_REVISION"
cat > "$work/out/source/BUILD.txt" <<'EOF'
The wine/ directory is the complete corresponding source, with the focus patch applied.
From this directory, on x86-64 Linux with Docker:

  docker build -t wine-focus-build -f build-support/wine-focus.Dockerfile build-support
  mkdir -p build
  docker run --rm --user "$(id -u):$(id -g)" -e XDG_CACHE_HOME=/build/cache \
    -v "$PWD/wine:/src" -v "$PWD/build:/build" \
    -v "$PWD/build-support/wine-focus-container.sh:/build.sh:ro" \
    wine-focus-build bash /build.sh

The result is build/objects/dlls/winex11.drv/winex11.so. Install only this module;
do not replace Valve's ntdll.so or win32u.so with incidental build dependencies.
The module is qualified only for the Proton build and companion hashes in the manifest.
Wine is LGPL-2.1-or-later; see wine/COPYING.LIB and individual source-file notices.
EOF
tar --zstd -cf "$work/wine-focus-7b3ceaf-r1-source.tar.zst" -C "$work/out/source" .
