#!/usr/bin/env python3
"""Persist Aurora's mixed-page boot switch through Omarchy's UKI generator."""
import argparse
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile


def kernel_supports_4k(root, release):
    image = root / f'usr/lib/modules/{release}/vmlinuz'
    if not image.is_file():
        return False
    data = image.read_bytes()
    start = data.find(b'IKCFG_ST')
    end = data.find(b'IKCFG_ED', start + 8)
    if start < 0 or end < 0:
        return False
    config = gzip.decompress(data[start + 8:end]).decode()
    return all(line in config.splitlines() for line in (
        'CONFIG_ARM64_16K_PAGES=y',
        'CONFIG_ARM64_USER4K_EXPERIMENTAL=y',
        'CONFIG_MM_SUBPAGE=y',
    ))


def boot_defaults(text):
    """Keep literal shell contents; never source configuration as Python/root."""
    found = False
    lines = []
    for line in text.splitlines(keepends=True):
        assignment = re.match(r'''^(\s*GRUB_CMDLINE_LINUX(_DEFAULT)?\s*=\s*)(["'])(.*)\3([ \t]*(?:#.*)?)\n?$''', line)
        if assignment:
            prefix, default, quote, value, suffix = assignment.groups()
            value = re.sub(r'(?<!\S)user4k=\S+\s*', '', value).rstrip()
            if not default:
                value = (value + ' user4k=on').lstrip()
                found = True
            line = prefix + quote + value + quote + suffix + '\n'
        elif re.match(r'^\s*GRUB_CMDLINE_LINUX(?:_DEFAULT)?\s*=', line):
            raise ValueError('Expected a quoted GRUB_CMDLINE_LINUX assignment')
        lines.append(line)
    if not found:
        lines.append('\nGRUB_CMDLINE_LINUX="user4k=on"\n')
    return ''.join(lines)


def embedded_cmdline(path):
    data = path.read_bytes()
    try:
        pe, = struct.unpack_from('<I', data, 0x3c)
        if data[pe:pe + 4] != b'PE\0\0':
            raise ValueError('invalid PE signature')
        count, = struct.unpack_from('<H', data, pe + 6)
        optional, = struct.unpack_from('<H', data, pe + 20)
        for index in range(count):
            pos = pe + 24 + optional + 40 * index
            if data[pos:pos + 8].rstrip(b'\0') == b'.cmdline':
                size, _, raw_size, offset = struct.unpack_from('<IIII', data, pos + 8)
                if size > raw_size or offset + size > len(data):
                    raise ValueError('truncated command line')
                return data[offset:offset + size].rstrip(b'\0').decode().split()
    except (struct.error, UnicodeError) as error:
        raise ValueError(f'Cannot inspect UKI {path}: {error}') from error
    raise ValueError(f'UKI has no embedded command line: {path}')


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=path.name + '.new-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            shutil.copymode(path, name)
        else:
            os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def enable(root=Path('/'), release=None):
    release = release or os.uname().release
    if not kernel_supports_4k(root, release):
        print(f'Kernel {release} lacks mixed-page support; keeping muvm available.')
        return False
    grub = root / 'etc/default/grub'
    limine = root / 'etc/default/limine'
    if not (root / 'var/lib/omarchy/limine.enabled').exists() or not grub.is_file() or not limine.is_file():
        print('Mixed-page boot setup requires Omarchy Limine; keeping muvm available.')
        return False
    match = re.search(r'''^ESP_PATH=["']?(/[^"'\n]*)["']?\s*$''', limine.read_text(), re.M)
    if not match:
        raise ValueError('Cannot find ESP_PATH in /etc/default/limine')
    esp = root / match[1].lstrip('/')
    config = esp / 'limine.conf'
    images = sorted((esp / 'EFI/Linux').glob('*.efi'))
    if not config.is_file() or not images:
        raise ValueError('No generated Limine boot configuration or UKIs')
    updated = boot_defaults(grub.read_text()).encode()

    def verified():
        current = sorted((esp / 'EFI/Linux').glob('*.efi'))
        if not current:
            raise ValueError('No generated UKIs after rebuild')
        for image in current:
            flags = [word for word in embedded_cmdline(image) if word.startswith('user4k=')]
            if flags != ['user4k=on']:
                raise ValueError(f'UKI does not enable user4k exactly once: {image}')
        return len(current)

    if grub.read_bytes() == updated:
        try:
            count = verified()
            print(f'Mixed-page boot option already installed in {count} UKIs.')
            return True
        except ValueError:
            pass
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup = root / f'var/lib/mac-steam-ultimate/boot-backups/{stamp}'
    backup.mkdir(parents=True, mode=0o700)
    files = [grub, limine, config, *images, *sorted((root / 'boot').glob('initramfs-*.img'))]
    for path in files:
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    try:
        atomic_write(grub, updated)
        subprocess.run(['limine-mkinitcpio'], check=True)
        count = verified()
    except BaseException:
        for path in files:
            atomic_write(path, (backup / path.relative_to(root)).read_bytes())
        for path in (esp / 'EFI/Linux').glob('*.efi'):
            if path not in images:
                path.unlink()
        raise
    print(f'Enabled user4k=on and verified {count} rebuilt UKIs. Reboot to activate it.')
    print(f'Previous boot files: {backup}')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run through the Steam installer as root')
    enable(release=args.kernel)
