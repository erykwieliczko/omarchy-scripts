#!/usr/bin/env python3
"""Package the qualified Steam tools without player prefixes or deployment state."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat_stack', PROJECT / 'runtime/compat_stack.py')
stack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stack)
BUILD_ID = '11.0-20261027b-r1'


def build(steam_root, component_prefix, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mac-stack-build-') as directory:
        work = Path(directory)
        # Use the checkout's launcher and integration with the installed binaries.
        prefix = work / 'components'
        prefix.mkdir()
        for name in ('fex', 'wine-focus'):
            (prefix / name).symlink_to(component_prefix / name)
        (prefix / 'runtime').symlink_to(PROJECT / 'runtime')
        tool = stack.prepare(work / 'Steam', [steam_root], prefix, from_steam=True)
        if tool is None:
            raise ValueError('Install the qualified x86 Proton, FEX tool and Steam Runtime 4 before building')
        shutil.rmtree(tool / 'runtime/var', ignore_errors=True)
        # Valve's shipped default_pfx contains required DirectX DLL links. It
        # is runtime data, not a player's game prefix, and must be retained.
        for path in tool.rglob('__pycache__'):
            shutil.rmtree(path)
        for pattern in ('*.valve-original*', '*.pre-ultimate', '*.lock'):
            for path in tool.rglob(pattern):
                if path.is_file() or path.is_symlink():
                    path.unlink()
        (tool / 'default-pending').unlink(missing_ok=True)
        metadata = json.loads((tool / 'stack.json').read_text())
        metadata['build_id'] = BUILD_ID
        metadata['sources'] = {
            'proton': {'steam_appid': 1493710, 'version': metadata['proton_version'],
                       'source': 'https://github.com/ValveSoftware/Proton/tree/experimental-11.0-20261027b'},
            'wine_focus': {'source': 'https://github.com/erykwieliczko/omarchy-scripts/tree/main/mac-steam/patches/wine'},
            'fex': {'steam_appid': 3127680, 'source': (component_prefix / 'fex/SOURCE.txt').read_text()},
            'runtime': {'steam_appid': 4183110, 'versions': metadata['runtime_versions']},
        }
        stack.atomic(tool / 'stack.json', json.dumps(metadata, indent=2) + '\n')
        shutil.copy2(component_prefix / 'wine-focus/manifest.json', tool / 'proton/mac-wine-focus-manifest.json')
        shutil.copytree(PROJECT / 'patches/wine', tool / 'proton/mac-wine-focus-patches')
        subprocess.run(['tar', '--sort=name', '--mtime=@0', '--owner=0', '--group=0', '--numeric-owner',
                        '-I', 'zstd -T4 -6', '-cf', str(output), '-C', str(tool), '.'], check=True)
    print(f'{stack.digest(output)}  {output.name}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steam-root', type=Path, required=True)
    parser.add_argument('--component-prefix', type=Path, default=Path('/opt/mac-steam-ultimate/current'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.steam_root.resolve(), args.component_prefix.resolve(), args.output.resolve())
