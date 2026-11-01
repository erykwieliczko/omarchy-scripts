#!/usr/bin/env python3
"""Install the measured M3 CPU policy and select the packaged display kernel."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

RELEASE = '7.2.11-11-dsc3-ARCH'
MODULE_SHA = '9029fe79689441fb0ee9ddce60dc6f74903b5fb9f95c58fc8dbe4d4ea24c2328'


def write(path, text):
    data = text.encode()
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + '.pre-mac-steam')
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    fd, name = tempfile.mkstemp(prefix=path.name + '.new-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def tune(root=Path('/')):
    write(root / 'etc/modprobe.d/90-mac-steam-m3.conf',
          '# Measured M3 Pro policy.\noptions kvm halt_poll_ns=0\n')
    write(root / 'etc/tmpfiles.d/mac-steam-m3.conf',
          '# Avoid spending host CPU polling idle guest vCPUs.\n'
          'w /sys/module/kvm/parameters/halt_poll_ns - - - - 0\n')
    # A conditional service keeps stock fallback kernels bootable: never pass
    # the private module parameter to drivers which do not implement it.
    write(root / 'etc/systemd/system/mac-steam-m3-panel.service',
          '[Unit]\nDescription=Enable qualified M3 panel swap timestamps\n'
          'After=systemd-modules-load.service\nBefore=display-manager.service\n'
          'ConditionPathExists=/sys/module/appledrm/parameters/t6030_swap_timestamps\n\n'
          '[Service]\nType=oneshot\n'
          "ExecStart=/usr/bin/sh -c 'printf Y > /sys/module/appledrm/parameters/t6030_swap_timestamps'\n\n"
          '[Install]\nWantedBy=multi-user.target\n')
    polling = root / 'sys/module/kvm/parameters/halt_poll_ns'
    if polling.exists():
        polling.write_text('0\n')
    # Only write this live if the running driver actually provides it.
    pacing = root / 'sys/module/appledrm/parameters/t6030_swap_timestamps'
    if pacing.exists():
        pacing.write_text('Y\n')


def select_kernel(root=Path('/')):
    defaults = root / 'etc/default/limine'
    text = defaults.read_text()
    match = re.search(r'^ESP_PATH=[\"\']?(/[^\"\'\n]*)[\"\']?\s*$', text, re.M)
    if not match:
        raise ValueError('Cannot find ESP_PATH in /etc/default/limine')
    esp = root / match[1].lstrip('/')
    config = esp / 'limine.conf'
    entries = config.read_text()
    # The distribution generates the entry and machine-specific root arguments.
    if not re.search(r'^\s+//linux-aurora-dsc\s*$', entries, re.M):
        raise ValueError('The packaged kernel has no generated Limine entry')
    group = re.search(r'^/\+([^\n]+)', entries, re.M)
    if not group:
        raise ValueError('Cannot identify the Omarchy boot menu')
    entry = f'default_entry: {group[1].strip()}/linux-aurora-dsc'
    if re.search(r'^default_entry:', entries, re.M):
        entries = re.sub(r'^default_entry:.*$', entry, entries, count=1, flags=re.M)
    else:
        entries = entry + '\n' + entries
    order = 'BOOT_ORDER="linux-aurora-dsc, linux-aurora, *, *fallback, Snapshots"'
    if re.search(r'^BOOT_ORDER=', text, re.M):
        text = re.sub(r'^BOOT_ORDER=.*$', order, text, count=1, flags=re.M)
    else:
        text += '\n' + order + '\n'
    module = root / f'usr/lib/modules/{RELEASE}/kernel/drivers/gpu/drm/apple/appledrm.ko'
    if hashlib.sha256(module.read_bytes()).hexdigest() != MODULE_SHA:
        raise ValueError('Installed display driver checksum differs from the qualified binary')
    uki = esp / 'EFI/Linux/omarchy_linux-aurora-dsc.efi'
    if not uki.is_file():
        raise ValueError('The packaged kernel UKI was not generated')
    # Verify the bootable image contains the repaired driver before selecting it.
    with tempfile.TemporaryDirectory(prefix='mac-steam-initrd-') as directory:
        import struct
        data = uki.read_bytes()
        pe, = struct.unpack_from('<I', data, 0x3c)
        if data[pe:pe+4] != b'PE\0\0':
            raise ValueError('Invalid UKI PE signature')
        count, = struct.unpack_from('<H', data, pe+6)
        opt, = struct.unpack_from('<H', data, pe+20)
        initrd = None
        for i in range(count):
            pos = pe+24+opt+40*i
            if data[pos:pos+8].rstrip(b'\0') == b'.initrd':
                size, _, _, offset = struct.unpack_from('<IIII', data, pos+8)
                initrd = data[offset:offset+size]
                if len(initrd) != size:
                    raise ValueError('Truncated UKI initrd')
        if initrd is None:
            raise ValueError('No initrd in the generated UKI')
        image = Path(directory) / 'initrd.img'
        image.write_bytes(initrd)
        subprocess.run(['lsinitcpio', '-x', str(image)], cwd=directory,
                       check=True, stdout=subprocess.DEVNULL)
        embedded = Path(directory) / module.relative_to(root)
        if hashlib.sha256(embedded.read_bytes()).hexdigest() != MODULE_SHA:
            raise ValueError('Generated UKI lacks the repaired display driver')
    write(defaults, text)
    write(config, entries)
    print('Verified display kernel and boot image; selected it for the next boot.')


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run host setup as root through the Steam installer.')
    if sys.argv[1:] == ['tune']:
        tune()
    elif sys.argv[1:] == ['select-kernel']:
        select_kernel()
    else:
        raise SystemExit('Usage: host-setup.py tune|select-kernel')
