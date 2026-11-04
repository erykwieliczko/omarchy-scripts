#!/usr/bin/env bash
# Publish committed setup-page sources after pushing them to GitHub.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
revision=$(git -C "$project" rev-parse HEAD)
remote=$(git -C "$project" remote get-url origin)
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
mkdir "$temporary/source"
# Use committed sources, so unrelated local changes never enter the website.
git -C "$project" archive "$revision" web setup.sh tools/build-site.py | tar -xf - -C "$temporary/source"
git init --quiet --initial-branch=gh-pages "$temporary/published"
git -C "$temporary/published" remote add origin "$remote"
if git -C "$temporary/published" ls-remote --exit-code --heads origin gh-pages >/dev/null; then
    git -C "$temporary/published" fetch --quiet --depth=1 origin gh-pages
    git -C "$temporary/published" checkout --quiet -B gh-pages FETCH_HEAD
    git -C "$temporary/published" rm -r --quiet --ignore-unmatch .
fi
python3 "$temporary/source/tools/build-site.py" --revision "$revision" --output "$temporary/published"
git -C "$temporary/published" add --all
git -C "$temporary/published" commit --quiet -m "Publish setup picker from $revision"
git -C "$temporary/published" push origin HEAD:refs/heads/gh-pages
printf 'Published source %s to gh-pages.\n' "$revision"
printf 'GitHub Pages: https://erykwieliczko.github.io/omarchy-scripts/\n'
