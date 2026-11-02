#!/usr/bin/env python3
"""Register a separate, pinned copy of the qualified Mac Proton stack."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time

TOOL_NAME = 'mac_steam_ultimate'
DISPLAY_NAME = 'Mac Steam Ultimate (FEX + Proton 11)'
DIRECTORY = 'mac-steam-ultimate'
TOKEN = re.compile(r'//[^\n]*|"(?:\\.|[^"\\])*"|[{}]')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_copy(source, target):
    # Steam marks some modules read-only. The private staging directory is not
    # published yet, so replace its entry instead of writing through that mode.
    target.unlink(missing_ok=True)
    shutil.copy2(source, target)


def atomic(path, data, mode=0o644):
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.new-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def nodes(text):
    """Read KeyValues spans so unrelated settings retain their exact bytes."""
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith('//')]

    def read(index, nested=False):
        result = []
        while index < len(tokens):
            key = tokens[index]
            if key.group() == '}':
                if not nested:
                    raise ValueError('Unexpected closing VDF brace')
                return result, index
            if not key.group().startswith('"') or index + 1 >= len(tokens):
                raise ValueError('Invalid VDF key')
            value = tokens[index + 1]
            node = {'key': key.group()[1:-1], 'start': key.start()}
            if value.group() == '{':
                children, end = read(index + 2, True)
                node.update(children=children, opening=value.end(), closing=tokens[end].start(),
                            end=tokens[end].end())
                index = end + 1
            elif value.group().startswith('"'):
                node.update(value=value.group()[1:-1], value_start=value.start(),
                            value_end=value.end(), end=value.end())
                index += 2
            else:
                raise ValueError('Invalid VDF value')
            result.append(node)
        if nested:
            raise ValueError('Unclosed VDF block')
        return result, index

    return read(0)[0]


def find(items, key):
    for item in items:
        if item['key'].lower() == key.lower():
            return item
        result = find(item.get('children', []), key)
        if result:
            return result
    return None


def default_config(text):
    mapping = find(nodes(text), 'CompatToolMapping')
    if mapping is None:
        steam = find(nodes(text), 'Steam')
        if steam is None or 'children' not in steam:
            raise ValueError('Steam configuration has no Steam settings block')
        insert = '\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n\t\t\t\t}\n'
        text = text[:steam['closing']] + insert + text[steam['closing']:]
        mapping = find(nodes(text), 'CompatToolMapping')
    replacements = []
    for appid, priority in (('0', '75'), ('813780', '250')):
        item = next((i for i in mapping['children'] if i['key'] == appid), None)
        # Preserve a deliberately selected per-game tool, other than our old setup.
        if item and appid != '0':
            name = next((i.get('value') for i in item.get('children', []) if i['key'] == 'name'), None)
            if name not in ('proton_experimental', TOOL_NAME):
                continue
        entry = (f'"{appid}"\n\t\t\t\t\t{{\n'
                 f'\t\t\t\t\t\t"name"\t\t"{TOOL_NAME}"\n'
                 '\t\t\t\t\t\t"config"\t\t""\n'
                 f'\t\t\t\t\t\t"priority"\t\t"{priority}"\n\t\t\t\t\t}}')
        if item:
            replacements.append((item['start'], item['end'], entry))
        else:
            replacements.append((mapping['opening'], mapping['opening'], '\n\t\t\t\t\t' + entry))
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    return text


def steam_running(root):
    for path in (root / 'steam.pid', root.parent.parent / '.steam/steam.pid',
                 Path.home() / '.steam/steam.pid'):
        try:
            pid = int(path.read_text())
            if Path(f'/proc/{pid}/comm').read_text().strip() == 'steam':
                return True
        except (OSError, ValueError):
            pass
    return False


def set_default(root, tool):
    if steam_running(root):
        return False
    config = root / 'config/config.vdf'
    if not config.is_file():
        config.parent.mkdir(parents=True, exist_ok=True)
        atomic(config, '"InstallConfigStore" { "Software" { "Valve" { "Steam" {} } } }\n', 0o600)
    old = config.read_text()
    new = default_config(old)
    if old != new:
        backup = config.with_name('config.vdf.pre-mac-stack')
        if not backup.exists():
            shutil.copy2(config, backup)
        atomic(config, new, config.stat().st_mode & 0o777)
    (tool / 'default-pending').unlink(missing_ok=True)
    return True


def arm_prefix(directory):
    system = directory / 'pfx/drive_c/windows/system32'
    for name in ('ntdll.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll'):
        path = system / name
        if 'aarch64-windows' in str(path.resolve()):
            return True
        try:
            with path.open('rb') as stream:
                header = stream.read(64)
                if len(header) != 64 or header[:2] != b'MZ':
                    continue
                stream.seek(struct.unpack_from('<I', header, 60)[0])
                pe = stream.read(6)
            if pe[:4] == b'PE\0\0' and len(pe) == 6 and struct.unpack_from('<H', pe, 4)[0] in (0xaa64, 0xa641):
                return True
        except OSError:
            pass
    return False


def migrate_aoe_prefix(root, libraries):
    """Keep ARM64 runtimes out of the new x86 prefix, retaining all old data."""
    if steam_running(root):
        return
    config = root / 'config/config.vdf'
    if not config.is_file():
        return
    mapping = find(nodes(config.read_text()), 'CompatToolMapping')
    if mapping is None:
        return
    entries = {n['key']: n for n in mapping['children']}
    selected = entries.get('813780', entries.get('0', {}))
    name = next((n.get('value') for n in selected.get('children', []) if n['key'] == 'name'), None)
    if name != TOOL_NAME:
        return
    for library in libraries:
        directory = library / 'steamapps/compatdata/813780'
        if not arm_prefix(directory):
            continue
        backup = directory.with_name(f'813780.arm64-before-mac-stack-{time.time_ns()}')
        directory.rename(backup)
        try:
            if (backup / 'fex-emu').is_dir():
                shutil.copytree(backup / 'fex-emu', directory / 'fex-emu')
            user = 'pfx/drive_c/users/steamuser'
            for name in ('Games', 'Documents', 'Saved Games'):
                source = backup / user / name
                target = directory / user / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_symlink():
                    target.symlink_to(os.readlink(source))
                elif source.is_dir():
                    shutil.copytree(source, target, symlinks=True)
            atomic(directory / 'mac-stack-migration.json', json.dumps({'original_prefix': str(backup)}, indent=2) + '\n')
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            backup.rename(directory)
            raise
        print(f'Preserved ARM64 AoE2 prefix at {backup}; saved games copied for x86 Proton.', flush=True)


def prepare_bundle(root, libraries, prefix, make_default=False):
    source = prefix / 'compat-stack'
    metadata = json.loads((source / 'stack.json').read_text())
    tool = root / 'compatibilitytools.d' / DIRECTORY
    previous = None
    pending = not tool.exists()
    if tool.exists():
        if not (tool / 'stack.json').is_file():
            raise ValueError(f'Refusing to replace an unrecognized custom tool: {tool}')
        previous = json.loads((tool / 'stack.json').read_text())
        pending = (tool / 'default-pending').exists()
    if previous is None or previous.get('build_id') != metadata['build_id']:
        if previous is not None and steam_running(root):
            return tool
        tool.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.mac-stack-', dir=tool.parent))
        backup = None
        try:
            subprocess.run(['cp', '-a', '--reflink=auto', str(source) + '/.', str(stage)], check=True)
            stage.chmod(0o755)
            (stage / 'default-pending').unlink(missing_ok=True)
            if pending:
                (stage / 'default-pending').touch()
            if previous is not None:
                backups = root / 'config/mac-steam-ultimate-backups'
                backups.mkdir(parents=True, exist_ok=True)
                backup = backups / f'stack-{time.time_ns()}'
                tool.rename(backup)
            try:
                stage.rename(tool)
            except Exception:
                if backup is not None:
                    backup.rename(tool)
                raise
            print(f'Installed compatibility tool: {DISPLAY_NAME}: {tool}', flush=True)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    if make_default or (tool / 'default-pending').exists():
        if set_default(root, tool):
            print(f'Steam default compatibility tool: {DISPLAY_NAME}', flush=True)
    migrate_aoe_prefix(root, libraries)
    return tool


def installed(libraries, appid, dirname):
    for library in libraries:
        manifest = library / f'steamapps/appmanifest_{appid}.acf'
        directory = library / 'steamapps/common' / dirname
        if (manifest.is_file() and re.search(r'"StateFlags"\s+"4"', manifest.read_text())
                and directory.is_dir()
                and not (library / f'steamapps/downloading/{appid}').exists()):
            return directory
    return None


def prepare(root, libraries, prefix, make_default=False, from_steam=False):
    if not from_steam and (prefix / 'compat-stack/stack.json').is_file():
        return prepare_bundle(root, libraries, prefix, make_default)
    tool = root / 'compatibilitytools.d' / DIRECTORY
    if not (tool / 'stack.json').is_file():
        sources = {
            'fex': installed(libraries, 3127680, 'FEX-Emu'),
            'proton': installed(libraries, 1493710, 'Proton - Experimental'),
            'runtime': installed(libraries, 4183110, 'SteamLinuxRuntime_4'),
        }
        manifest_path = prefix / 'wine-focus/manifest.json'
        if not all(sources.values()) or not manifest_path.is_file():
            return None
        manifest = json.loads(manifest_path.read_text())
        proton = sources['proton']
        if ((proton / 'version').read_text().strip() != manifest['proton_version']
                or any(digest(proton / p) != h for p, h in manifest['companions'].items())):
            return None
        driver = proton / 'files/lib/wine/x86_64-unix/winex11.so'
        if digest(driver) not in (manifest['original_sha256'], manifest['patched_sha256']):
            return None
        if digest(prefix / 'wine-focus/winex11.so') != manifest['patched_sha256']:
            raise ValueError('Private Wine focus module checksum failed')
        tool.parent.mkdir(parents=True, exist_ok=True)
        if tool.exists():
            raise ValueError(f'Refusing to replace an unrecognized custom tool: {tool}')
        stage = Path(tempfile.mkdtemp(prefix='.mac-stack-', dir=tool.parent))
        try:
            for name, source in sources.items():
                (stage / name).mkdir()
                subprocess.run(['cp', '-a', '--reflink=auto', str(source) + '/.', str(stage / name)], check=True)
            if any(digest(stage / 'proton' / p) != h for p, h in manifest['companions'].items()):
                raise ValueError('Copied Proton companion modules do not match the qualified ABI')
            # Runtime deployment state and per-user overrides are not part of our build.
            shutil.rmtree(stage / 'runtime/var', ignore_errors=True)
            shutil.rmtree(stage / 'proton/__pycache__', ignore_errors=True)
            (stage / 'proton/user_settings.py').unlink(missing_ok=True)
            replace_copy(prefix / 'wine-focus/winex11.so', stage / 'proton/files/lib/wine/x86_64-unix/winex11.so')
            for name in ('FEX', 'FEXServer'):
                replace_copy(prefix / 'fex/bin' / name, stage / 'fex/usr/bin' / name)
            replace_copy(prefix / 'fex/bin/FEXCompatTool', stage / 'fex/FEXCompatTool')
            shutil.copy2(prefix / 'fex/bin/FEXServerManager', stage / 'fex/usr/bin/FEXServerManager.native')
            replace_copy(prefix / 'runtime/fex-server-manager', stage / 'fex/usr/bin/FEXServerManager')
            shutil.copy2(prefix / 'runtime/mac-proton', stage / 'mac-proton')
            for name in ('SOURCE.txt', 'patches', 'licenses'):
                source = prefix / 'fex' / name
                if source.is_dir():
                    shutil.copytree(source, stage / 'fex' / name, dirs_exist_ok=True)
                elif source.is_file():
                    shutil.copy2(source, stage / 'fex' / name)
            # The copied app overrides expand relative to this copy of the FEX tool.
            stack = {'format': 1, 'name': DISPLAY_NAME, 'proton_version': manifest['proton_version'],
                     'fex_sha256': digest(stage / 'fex/usr/bin/FEX'),
                     'wine_x11_sha256': digest(stage / 'proton/files/lib/wine/x86_64-unix/winex11.so'),
                     'runtime_versions': (stage / 'runtime/VERSIONS.txt').read_text(),
                     'sources': {k: str(v) for k, v in sources.items()}}
            # Abort if a download changed the source during the snapshot.
            if (proton / 'version').read_text().strip() != manifest['proton_version']:
                raise ValueError('Proton changed while copying the stack; retry after its update')
            atomic(stage / 'stack.json', json.dumps(stack, indent=2) + '\n')
            atomic(stage / 'toolmanifest.vdf', '"manifest"\n{\n  "version" "2"\n  "commandline" "/mac-proton %verb%"\n  "use_sessions" "1"\n  "compatmanager_layer_name" "proton"\n}\n')
            atomic(stage / 'compatibilitytool.vdf', '"compatibilitytools"\n{\n  "compat_tools"\n  {\n    "' + TOOL_NAME + '"\n    {\n      "install_path" "."\n      "display_name" "' + DISPLAY_NAME + '"\n      "from_oslist" "windows"\n      "to_oslist" "linux"\n    }\n  }\n}\n')
            (stage / 'default-pending').touch()
            stage.chmod(0o755)
            stage.rename(tool)
            print(f'Installed compatibility tool: {DISPLAY_NAME}: {tool}', flush=True)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    if make_default or (tool / 'default-pending').exists():
        if set_default(root, tool):
            print(f'Steam default compatibility tool: {DISPLAY_NAME}', flush=True)
    return tool


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steam-root', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, default=Path('/opt/mac-steam-ultimate/current'))
    parser.add_argument('--set-default', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('run as the Steam desktop user')
    # The preparer supplies all libraries; standalone installation also reads them.
    roots = [args.steam_root]
    folders = args.steam_root / 'steamapps/libraryfolders.vdf'
    if folders.is_file():
        roots.extend(Path(s.replace('\\\\', '\\').replace('\\"', '"')) for s in
                     re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', folders.read_text()))
    if prepare(args.steam_root, list(dict.fromkeys(roots)), args.prefix, args.set_default) is None:
        raise SystemExit('The qualified x86 Proton, FEX and Steam Runtime 4 must be fully installed first.')
