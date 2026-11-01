#!/usr/bin/env bash
# Bundle complete corresponding source with an offline makepkg source recipe.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")" && pwd)
base=${1:?Usage: kernel-source.sh BASE_GIT_CHECKOUT OUTPUT_ARCHIVE}
output=${2:?Missing output archive}
commit=3bdf11d3acb6ea1511b0611ddd40ac5336b7b215
[[ $(git -C "$base" rev-parse HEAD) == "$commit" ]]
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
cp -a "$project/kernel/." "$temporary/"
git -C "$base" archive --prefix=linux/ "$commit" | zstd -T4 -10 -o "$temporary/linux-base.tar.zst"
python3 - "$temporary" <<'PY'
from pathlib import Path
import hashlib, sys
root = Path(sys.argv[1])
recipe = root / 'PKGBUILD'
text = recipe.read_text().replace('"linux::git+https://github.com/omacom/linux-aurora.git#commit=${_commit}"', 'linux-base.tar.zst')
text = text.replace("'SKIP'", "'"+hashlib.sha256((root/'linux-base.tar.zst').read_bytes()).hexdigest()+"'", 1)
recipe.write_text(text)
(root/'SOURCE.txt').write_text('omacom/linux-aurora 3bdf11d3acb6ea1511b0611ddd40ac5336b7b215\nComplete base source plus six patches. Rebuild on ARM64 with: makepkg --syncdeps\nKernel release intentionally remains 7.2.11-11-dsc3-ARCH; package revision is 3.1.\n')
PY
tar --zstd -cf "$output" -C "$temporary" .
sha256sum "$output"
