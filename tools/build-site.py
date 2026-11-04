#!/usr/bin/env python3
"""Build a static Pages artifact with the dispatcher pinned to its source commit."""
import argparse
from pathlib import Path
import re
import shutil


def build(root, destination, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use the full Git commit SHA for the published installer')
    destination.mkdir(parents=True, exist_ok=True)
    for source in (root / 'web').iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    script = (root / 'setup.sh').read_text()
    marker = '    local revision=main\n'
    if script.count(marker) != 1:
        raise ValueError('Cannot locate the dispatcher revision to pin')
    (destination / 'install.sh').write_text(script.replace(marker, f'    local revision={revision}\n'))
    (destination / '.nojekyll').touch()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output, args.revision)
