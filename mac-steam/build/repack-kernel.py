#!/usr/bin/env python3
"""Package the qualified kernel image/modules with the tested display module.

The base kernel image is unchanged. Full corresponding source and an independent
makepkg rebuild recipe accompany the release. No installation is performed.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

base, module, output = map(Path, sys.argv[1:])
release = '7.2.11-11-dsc3-ARCH'
assert hashlib.sha256(module.read_bytes()).hexdigest() == '9029fe79689441fb0ee9ddce60dc6f74903b5fb9f95c58fc8dbe4d4ea24c2328'
with tempfile.TemporaryDirectory(prefix='mac-steam-kernel-') as tmp:
    root = Path(tmp)
    subprocess.run(['bsdtar', '-xf', str(base.resolve()), '-C', tmp], check=True)
    target = root / f'usr/lib/modules/{release}/kernel/drivers/gpu/drm/apple/appledrm.ko'
    assert target.is_file()
    assert 'pkgver = 7.2.11.aurora11-3\n' in (root / '.PKGINFO').read_text()
    shutil.copyfile(module, target)
    target.chmod(0o644)
    doc = root / 'usr/share/doc/mac-steam-m3-kernel'
    doc.mkdir(parents=True)
    shutil.move(root / '.BUILDINFO', doc / 'base-kernel.BUILDINFO')
    (doc / 'repack.json').write_text(json.dumps({
        'base_package_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
        'display_module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
        'kernel_source': 'omacom/linux-aurora@3bdf11d3acb6ea1511b0611ddd40ac5336b7b215',
        'kernel_release': release,
        'changes': 'Private DSC/hold-link/Wi-Fi kernel plus native framebuffer retirement and T6030 timestamp fixes.',
    }, indent=2)+'\n')
    info = (root / '.PKGINFO').read_text()
    info = info.replace('pkgver = 7.2.11.aurora11-3\n', 'pkgver = 7.2.11.aurora11-3.1\n')
    info = info.replace('pkgdesc = The kernel and modules', 'pkgdesc = Qualified M3 Pro kernel with AoE2 display fixes')
    info = re.sub(r'^size = .*$', 'size = '+str(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())), info, flags=re.M)
    (root / '.PKGINFO').write_text(info)
    (root / '.MTREE').unlink()
    members = sorted(p.name for p in root.iterdir())
    mtree = subprocess.check_output(['bsdtar', '-cf', '-', '--format=mtree', '--uid', '0', '--gid', '0',
        '--options=!all,use-set,type,uid,gid,mode,time,size,sha256,link', *members], cwd=tmp)
    import gzip
    (root / '.MTREE').write_bytes(gzip.compress(mtree, mtime=0))
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['bsdtar', '--zstd', '-cf', str(output.resolve()), '--uid', '0', '--gid', '0',
                    '.PKGINFO', '.MTREE', 'usr'], cwd=tmp, check=True)
print(output, hashlib.sha256(output.read_bytes()).hexdigest())
