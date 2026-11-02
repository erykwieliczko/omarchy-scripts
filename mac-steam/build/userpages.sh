#!/usr/bin/env bash
# Package the unmodified Aurora launcher and its complete corresponding source.
set -euo pipefail
source_tree=${1:?Usage: userpages.sh KERNEL_GIT_CHECKOUT OUTPUT_DIRECTORY}
output=${2:?Missing output directory}
commit=3bdf11d3acb6ea1511b0611ddd40ac5336b7b215
mkdir -p "$output"
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
chmod 755 "$stage"
mkdir -p "$stage/bin" "$stage/source"
git -C "$source_tree" archive "$commit" \
    tools/aurora-userpages include/uapi/linux/prctl.h COPYING LICENSES/preferred/GPL-2.0 \
    LICENSES/exceptions/Linux-syscall-note | tar -xf - -C "$stage/source"
make -C "$stage/source/tools/aurora-userpages" CC="${CC:-cc}" CFLAGS='-O2 -Wall -Wextra'
install -m755 "$stage/source/tools/aurora-userpages/userpages" "$stage/bin/userpages"
rm "$stage/source/tools/aurora-userpages/userpages"
printf 'Unmodified omacom/linux-aurora %s\nRebuild: make -C source/tools/aurora-userpages\n' \
    "$commit" > "$stage/SOURCE.txt"
tar --zstd -cf "$output/userpages-3bdf11d3-r1-aarch64.tar.zst" -C "$stage" .
sha256sum "$output/userpages-3bdf11d3-r1-aarch64.tar.zst"
