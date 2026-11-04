#!/usr/bin/env python3
"""Install Aurora's published Flatpak driver extension for Aurora Mesa hosts."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

SOURCE = ('https://github.com/aurora-silicon/alarm-aurora/releases/download/'
          'testing-20261103.9/aurora-flatpak-gl-1_26.3.0_devel.202611030515.05ddb00f5ca-1-aarch64.pkg.tar.xz')
SHA256 = 'ed0c0f260df6aa1201d4346dcbbf4c402fd9e6d4001c1a812cb6728d5fffd151'
DRIVER = 'org.freedesktop.Platform.GL.aurora'
GL = '/usr/lib/aarch64-linux-gnu/GL'
LOADER_DEFAULTS = {
    'VK_DRIVER_FILES': f'{GL}/vulkan/icd.d/asahi_icd.aarch64.json:{GL}/vulkan/icd.d/lvp_icd.aarch64.json',
    '__EGL_VENDOR_LIBRARY_FILENAMES': f'{GL}/glvnd/egl_vendor.d/50_mesa.json',
    'LIBGL_DRIVERS_PATH': f'{GL}/lib/dri',
}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def missing_loader_defaults(overrides):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_string(overrides)
    existing = config['Environment'] if config.has_section('Environment') else {}
    return {key: value for key, value in LOADER_DEFAULTS.items() if key not in existing}


def install(account):
    if subprocess.run(['pacman', '-Q', 'mesa-aurora'], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        print('Flatpak uses the distribution graphics driver (Aurora Mesa is not installed).')
        return
    user = pwd.getpwnam(account)
    if user.pw_uid < 1000:
        raise RuntimeError('Use a regular desktop account')
    def user_run(arguments, **kwargs):
        return subprocess.run(['runuser', '-u', account, '--', 'env',
                               f'XDG_RUNTIME_DIR=/run/user/{user.pw_uid}',
                               f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{user.pw_uid}/bus',
                               'FLATPAK_GL_DRIVERS=aurora:default:host', *arguments],
                              check=True, text=True, **kwargs)
    cache = Path('/var/cache/omarchy-gnome')
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'aurora-flatpak-gl-05ddb00f.pkg.tar.xz'
    if not archive.exists() or digest(archive) != SHA256:
        partial = archive.with_suffix('.partial')
        subprocess.run(['curl', '--fail', '--location', '--retry', '3', '--proto', '=https',
                        '--tlsv1.2', SOURCE, '-o', str(partial)], check=True)
        if digest(partial) != SHA256:
            partial.unlink(missing_ok=True)
            raise RuntimeError('Aurora Flatpak graphics archive checksum failed')
        partial.replace(archive)
    destination = Path('/usr/local/share/omarchy-gnome/flatpak-gl')
    repo = destination / 'usr/share/aurora-flatpak-gl/repo'
    receipt = destination / 'source.json'
    if not receipt.exists() or json.loads(receipt.read_text()).get('sha256') != SHA256:
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run(['tar', '-xJf', str(archive), '--no-same-owner', '--no-same-permissions',
                        '-C', str(destination), 'usr/share/aurora-flatpak-gl/repo',
                        'usr/share/licenses/aurora-flatpak-gl/LICENSE'], check=True)
        receipt.write_text(json.dumps({'source': SOURCE, 'sha256': SHA256,
                                       'upstream': 'https://github.com/aurora-silicon/alarm-aurora'}, indent=2) + '\n')
    remote = 'omarchy-gnome-aurora-gl'
    names = user_run(['flatpak', 'remotes', '--user', '--columns=name'], capture_output=True).stdout.splitlines()
    if remote in names:
        user_run(['flatpak', 'remote-modify', '--user', '--url=' + repo.as_uri(), remote])
    else:
        # The containing archive is checksum-verified above; this local repo
        # carries the upstream build's unsigned Flatpak objects.
        user_run(['flatpak', 'remote-add', '--user', '--no-gpg-verify', '--no-enumerate',
                  '--no-use-for-deps', remote, repo.as_uri()])
    for branch in ('25.08', '26.08'):
        ref = f'runtime/{DRIVER}/aarch64/{branch}'
        if not (repo / 'refs/heads' / ref).is_file():
            raise RuntimeError(f'Aurora Flatpak archive has no {ref}')
        user_run(['flatpak', 'install', '--user', '--noninteractive', '-y', '--or-update', remote, ref])
        user_run(['flatpak', 'pin', '--user', ref])
    current = user_run(['flatpak', 'override', '--user', '--show'], capture_output=True).stdout
    state = Path(user.pw_dir) / '.local/state/omarchy-gnome'
    user_run(['python3', '-c',
              'from pathlib import Path; import sys; '
              'p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); '
              'p.write_text(sys.argv[2]) if not p.exists() else None',
              str(state / 'flatpak-overrides-before.ini'), current])
    for key, value in missing_loader_defaults(current).items():
        user_run(['flatpak', 'override', '--user', f'--env={key}={value}'])
    user_run(['python3', '-c',
              'from pathlib import Path; import sys; '
              'p=Path.home()/".config/environment.d/60-omarchy-gnome-flatpak-gl.conf"; '
              'p.parent.mkdir(parents=True,exist_ok=True); '
              'p.write_text(sys.argv[1])',
              'FLATPAK_GL_DRIVERS=${FLATPAK_GL_DRIVERS:-aurora:default:host}\n'])
    (destination / 'enabled').touch()
    print('Aurora Flatpak graphics installed; host Mesa and the kernel are unchanged.')


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run setup-flatpak-gl.py as root from the GNOME installer')
    install(sys.argv[1])
