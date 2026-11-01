#!/usr/bin/env python3
"""Keep the tested FEX binaries and AoE-only Vulkan bridge across Steam updates."""
import argparse
import fcntl
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

PREFIX = Path('/opt/mac-steam-ultimate/current')


def atomic_bytes(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.new-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge_json(path, update):
    data = json.loads(path.read_text()) if path.exists() else {}
    old = json.dumps(data, sort_keys=True)
    for key, value in update.items():
        data.setdefault(key, {}).update(value)
    if old != json.dumps(data, sort_keys=True):
        if path.exists() and not path.with_name(path.name + '.pre-ultimate').exists():
            shutil.copy2(path, path.with_name(path.name + '.pre-ultimate'))
        atomic_bytes(path, (json.dumps(data, indent=2) + '\n').encode())


def libraries(root):
    result = [root]
    path = root / 'steamapps/libraryfolders.vdf'
    if path.exists():
        # Steam escapes backslashes and quotes in VDF strings.
        for value in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', path.read_text()):
            candidate = Path(value.replace('\\\\', '\\').replace('\\"', '"'))
            if candidate not in result:
                result.append(candidate)
    return result


def tool_in_use(tool):
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            executable = os.readlink(entry / 'exe')
            if executable.startswith(str(tool) + '/'):
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return False


def proton_in_use(proton):
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            # A host invocation cannot inspect processes inside an existing VM.
            if os.sysconf('SC_PAGE_SIZE') != 4096:
                argv = (entry / 'cmdline').read_bytes().split(b'\0')
                if argv and Path(os.fsdecode(argv[0])).name == 'muvm':
                    return True
            if str(proton) + '/' in (entry / 'maps').read_text():
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return False


def prepare_proton(library, seen):
    private = PREFIX / 'wine-focus'
    if not (private / 'manifest.json').is_file():
        return
    proton = library / 'steamapps/common/Proton - Experimental'
    appmanifest = library / 'steamapps/appmanifest_1493710.acf'
    if (not appmanifest.exists()
            or not re.search(r'"StateFlags"\s+"4"', appmanifest.read_text())
            or (library / 'steamapps/downloading/1493710').exists()):
        return
    manifest = json.loads((private / 'manifest.json').read_text())
    driver = proton / 'files/lib/wine/x86_64-unix/winex11.so'
    companions = {proton / name: digest for name, digest in manifest['companions'].items()}
    paths = [driver, proton / 'version', *companions]
    if not all(path.is_file() for path in paths):
        return
    signature = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns) for p in paths)
    key = 'proton:' + str(proton)
    if seen.get(key) == signature:
        return
    digest = hashlib.sha256(driver.read_bytes()).hexdigest()
    qualified = ((proton / 'version').read_text().strip() == manifest['proton_version']
                 and all(hashlib.sha256(p.read_bytes()).hexdigest() == value
                         for p, value in companions.items()))
    backup = driver.with_name(driver.name + '.valve-original-focus')
    if not qualified:
        # A partial Proton update can retain our modified file. Restore the
        # original module for that file before leaving an unqualified build alone.
        if digest == manifest['patched_sha256']:
            if proton_in_use(proton):
                return
            if not backup.exists() or hashlib.sha256(backup.read_bytes()).hexdigest() != manifest['original_sha256']:
                raise ValueError('Cannot restore the original Proton X11 driver')
            atomic_bytes(driver, backup.read_bytes(), 0o755)
        print(f'Proton focus repair needs qualification for: {proton}', file=sys.stderr, flush=True)
    elif digest == manifest['original_sha256']:
        if proton_in_use(proton):
            return
        data = (private / 'winex11.so').read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['patched_sha256']:
            raise ValueError('Private Proton X11 driver checksum failed')
        if not backup.exists():
            shutil.copy2(driver, backup)
        elif hashlib.sha256(backup.read_bytes()).hexdigest() != manifest['original_sha256']:
            raise ValueError('Unexpected original Proton X11 driver backup')
        atomic_bytes(driver, data, 0o755)
        print(f'Installed Wine focus repair: {proton}', flush=True)
    elif digest != manifest['patched_sha256']:
        print(f'Leaving an unrecognized Proton X11 driver unchanged: {proton}', file=sys.stderr, flush=True)
    seen[key] = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns) for p in paths)


def prepare(root, seen):
    paths = libraries(root)
    for library in paths:
        prepare_proton(library, seen)
        tool = library / 'steamapps/common/FEX-Emu'
        binaries = {tool / 'usr/bin' / name: PREFIX / 'fex/bin' / name
                    for name in ('FEX', 'FEXServer')}
        binaries[tool / 'usr/bin/FEXServerManager'] = PREFIX / 'runtime/fex-server-manager'
        binaries[tool / 'FEXCompatTool'] = PREFIX / 'fex/bin/FEXCompatTool'
        manifest = library / 'steamapps/appmanifest_3127680.acf'
        ready = (manifest.exists() and re.search(r'"StateFlags"\s+"4"', manifest.read_text())
                 and all(p.is_file() for p in binaries)
                 and not (library / 'steamapps/downloading/3127680').exists())
        if not ready:
            continue
        signature = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns)
                          for p in binaries)
        if seen.get(str(tool)) != signature and not tool_in_use(tool):
            for target, source in binaries.items():
                source_data = source.read_bytes()
                if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source_data).digest():
                    backup = target.with_name(target.name + '.valve-original')
                    if not backup.exists():
                        shutil.copy2(target, backup)
                    atomic_bytes(target, source_data, 0o755)
                    print(f'Installed AoE2 FEX: {target}', flush=True)
            seen[str(tool)] = tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns)
                                    for p in binaries)
        if not tool_in_use(tool):
            # pressure-vessel's main graphics provider contains x86 Mesa.
            # Point only AoE's native Vulkan thunk at the ARM host driver.
            # Core config overrides belong in ConfigTemplate: loading them
            # from the executable's late ThunksDB profile is insufficient.
            native_icd = tool / 'asahi-native.json'
            icd_data = (json.dumps({
                'file_format_version': '1.0.1',
                'ICD': {'api_version': '1.4.363', 'library_arch': '64',
                        'library_path': '/run/host/usr/lib/libvulkan_asahi.so'},
            }, indent=2) + '\n').encode()
            if not native_icd.exists() or native_icd.read_bytes() != icd_data:
                atomic_bytes(native_icd, icd_data)
            template_path = tool / 'ConfigTemplate.json'
            template = json.loads(template_path.read_text())
            aoe_override = dict(template.get('AppOverrides', {}).get('AoE2DE_s.exe', {}))
            aoe_override['HostEnv'] = 'VK_DRIVER_FILES=@FEX_COMPAT_TOOL@/asahi-native.json'
            merge_json(template_path, {'Config': {
                'NeedsSeccomp': '1', 'SMCHotPageFaults': '32', 'ProfileStats': '0',
                'DiskCache': '0', 'X87ReducedPrecision': '1'},
                'AppOverrides': {'AoE2DE_s.exe': aoe_override}})

    # Prepare the default library in advance; apply to other libraries once AoE exists there.
    overlays = ['/usr/lib/libvulkan.so', '/usr/lib/libvulkan.so.1', '/lib/libvulkan.so.1',
                '/usr/lib32/libvulkan.so', '/usr/lib32/libvulkan.so.1',
                '/run/gfx/main/usr/lib/libvulkan.so.1',
                '@PREFIX_LIB@/libvulkan.so', '@PREFIX_LIB@/libvulkan.so.1']
    for directory in ('usr/lib', 'usr/lib32'):
        for path in glob.glob('/run/fex-emu/rootfs/' + directory + '/libvulkan.so*'):
            name = Path(path).name
            overlays.extend(['/' + directory + '/' + name,
                             '/run/gfx/main/' + directory + '/' + name])
    database = {'DB': {'AoEVulkan': {'Library': 'libvulkan-guest.so',
                                    'Overlay': sorted(set(overlays))}}}
    for library in paths:
        if library != root and not (library / 'steamapps/appmanifest_813780.acf').exists():
            continue
        config = library / 'steamapps/compatdata/813780/fex-emu'
        merge_json(config / 'ThunksDB.json', database)
        merge_json(config / 'AppConfig/Steam_813780_AoE2DE_s.exe.json',
                   {'ThunksDB': {'AoEVulkan': 1}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('run as the Steam desktop user')
    root = Path.home() / '.steam/steam'
    root = root.resolve() if root.exists() else Path(os.environ.get(
        'XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'Steam'
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'mac-steam-ultimate'
    cache.mkdir(parents=True, exist_ok=True)
    seen = {}
    # Each pass locks briefly, allowing --prepare while another client watches.
    with (cache / 'prepare.lock').open('w') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
                prepare(root, seen)
            except (OSError, ValueError) as error:
                print(f'Steam Ultimate preparation: {error}', file=sys.stderr, flush=True)
                if not args.watch:
                    return 1
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
            if not args.watch:
                return 0
            time.sleep(2)


if __name__ == '__main__':
    sys.exit(main())
