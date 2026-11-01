# Install Mac Steam Ultimate WIP

The native ARM Steam client runs inside **muvm's 4K-page Linux guest** on the Mac's 16K-page host. Windows games use Proton and FEX. The private ARM Mesa stack is bind-mounted over the guest's Mesa libraries during VM startup. The x86 Mesa stacks are 4K EROFS overlays on the Arch FEX rootfs. These mounts belong to the guest kernel.

## Pinned components

| Component | Source/version |
| --- | --- |
| FEX | [StonkGuy/FEX](https://github.com/StonkGuy/FEX/tree/b608a47670de0ce6cca519858c2e57a2590344da), `b608a47670de0ce6cca519858c2e57a2590344da`, from `eac-2610` |
| FEX local fixes | `patches/fex/0002`–`0004`: invalid opcode handling on hot SMC pages, larger hot-page tracking, constant-time IR block append |
| Mesa, ARM64 + x86-64 + i386 | [omacom/mesa](https://github.com/omacom/mesa/tree/672657e05e6b382a0203975f7a26c46f9a674973), `672657e05e6b382a0203975f7a26c46f9a674973` |
| Mesa local fixes | `patches/mesa/0001`–`0005`: M3 G15 virtio wire conversion, queue priority limits, VM status handling, placed mapping bounds, host-backed memory accounting |
| Wine focus repair | `ValveSoftware/wine` `7b3ceaf8644bb5d57140903e12897efac69be16a` + `patches/wine/0001`, qualified for Proton Experimental `11.0-20261027b` |
| M3 kernel | `omacom/linux-aurora` `3bdf11d3acb6ea1511b0611ddd40ac5336b7b215`, package `linux-aurora-dsc 7.2.11.aurora11-3.1`, kernel release `7.2.11-11-dsc3-ARCH` |
| M3 kernel fixes | DSC sequencing, display/audio hold-link, Wi-Fi country map, native framebuffer retirement, optional T6030 swap timestamps |
| Binary assets | GitHub release `mac-steam-ultimate-wip-v0.2.0`, pinned by [SHA-256](artifacts.sha256) |

FEX is built with Steam support, bundled fmt/xxhash, release optimization and all three local fixes. The tested configuration enables seccomp fidelity and uses `SMCHotPageFaults=32`, reduced x87 precision and no disk code cache. Profiling is disabled for normal use.

The distribution's `FEX-Emu` package remains a muvm prerequisite. **The Steam VM and Valve FEX compatibility tool use the private patched FEX**, rather than that package's older executable. The guest binfmt registration points directly at the private FEX binary.

Steam, Proton, muvm, libkrun, virglrenderer and base rootfs/overlay packages come from configured Omarchy/Asahi repositories or Valve. They continue receiving their normal updates. This release pins our FEX/Mesa sources and binaries, not the entire operating system or proprietary Steam client.

Baseline used on 2026-10-31: native `omarchy/steam 1.0.0.87-1`, client build `1792618285`, `muvm 0.7.0-1`, `libkrun 1.19.7-1`, `virglrenderer 1.3.0-2`, `fex-emu-rootfs-arch 20260318-1`, base Mesa overlays `26.2.3-1`, host `mesa-aurora/vulkan-aurora 26.3.0-devel` at the same Mesa base commit, kernel `7.2.11-11-dsc3-ARCH`.

## Integration

Files live under `/opt/mac-steam-ultimate/releases/`; `current` selects the active installation and `previous` retains the preceding one. Distribution-owned Mesa/FEX executables are preserved on the host. Steam's user desktop entry launches `/usr/local/bin/steam-mac-ultimate`; its previous entry is saved as `steam.desktop.pre-ultimate`. `/usr/local/bin/steam` and `/usr/local/bin/omarchy-launch-steam` route command-line launches, game shortcuts and Omarchy bindings through the same setup; existing local commands are backed up as `*.pre-ultimate`. Inside the 4K guest the wrapper selects `/usr/bin/steam` directly.

Valve's FEX compatibility tool (Steam app `3127680`) supplies the Vulkan guest/host bridge. `runtime/prepare.py` runs before Steam and watches for completed tool downloads while Steam runs. It replaces the four FEX executables atomically and saves the first originals as `*.valve-original`. It defers changes when the tool is downloading or running. Existing JSON settings are merged and backed up as `*.pre-ultimate`.

For AoE2 only (app `813780`, executable `AoE2DE_s.exe`), the preparer adds the Arch library paths missing from the thunk database and enables the native Vulkan bridge through FEX's Steam application configuration. It discovers additional Steam library paths, including paths containing spaces. Other games receive the shared FEX correctness fixes; their Vulkan bridge settings are left to Steam.

AoE2's native bridge also needs an ARM driver manifest inside pressure-vessel. Its default graphics provider describes the x86 Mesa overlays, so an ARM loader following that catalog cannot load the driver. The preparer writes `FEX-Emu/asahi-native.json`, pointing at the private guest driver exported at `/run/host/usr/lib/libvulkan_asahi.so`. A `ConfigTemplate.json` application override selects it with FEX's `HostEnv` for `AoE2DE_s.exe`; Valve expands the tool-path placeholder into each game's configuration. The manifest and override are restored after tool updates. Driver selection is separate from the x86 overlays, which remain installed.

No account credentials or game files are bundled. First use requires Steam sign-in and the normal game/runtime downloads. The installer leaves resolution and game graphics settings to the player.

### Clean-install M3 display and CPU setup

The 14-inch M3 Pro (`apple,j514s`) no longer needs the previous machine's custom
build directory. The installer downloads the qualified complete kernel package
and corresponding source, installs it with pacman, checks the generated UKI's
embedded display-module checksum, and selects the new Limine entry. Existing
machine-specific root/encryption arguments are generated by Omarchy's normal
hooks and preserved. The distribution kernel remains installed as a fallback.
Reboot once after installing both KDE and Steam.

The kernel image and other modules are from the tested DSC kernel. The repacked
package replaces only `appledrm.ko` with the hardware-tested retirement/timestamp
build and records its base-package and module hashes under
`/usr/share/doc/mac-steam-m3-kernel/`. Package revision `3.1` intentionally keeps
the qualified kernel release string. The source bundle contains the complete
base source, six patches and an offline-source makepkg recipe.

On the M3, `90-mac-steam-m3.conf` and `mac-steam-m3.conf` persist KVM
`halt_poll_ns=0`; the live value is applied too. Matched earlier native-menu
measurements reduced VM CPU from about 3.37 to 1.49 cores without reducing the
roughly 58 presentations/s. A conditional `mac-steam-m3-panel.service` enables
the packaged driver's internal-panel timestamp option before graphical login.
It skips stock fallback drivers lacking that option. Native-cube tests measured
about 117 panel swaps/s with the option versus 59 without; this is not an AoE2
120 FPS claim. M1 installs skip the M3 kernel and tuning assets.

Experimental FEX short-validation and Mesa image-compression builds remain
separate. In the 6048×3928 stress test the compression candidate improved queued
frames by about 33%, but the overnight process was OOM-killed after roughly two
hours. Allocation ownership is unresolved, so it is not promoted by this release.
Profiling, timing hooks and disk JIT caching stay disabled in normal installation.

### Keyboard focus

Steam can advance X11's last-focus-change timestamp while Wine is responding to `WM_TAKE_FOCUS`, for example when a game replaces a splash window. The server silently rejects Wine's older timestamp, leaving keyboard focus on Steam despite KDE showing the game as active. This happens through XWayland; the KDE desktop itself uses Wayland.

The local Wine source patch checks whether the request actually acquired focus. If it failed and the window manager still selects that window, Wine obtains a fresh server timestamp from an unmapped InputOnly window, checks the selection again, and retries once. A later focus change still supersedes the retry through normal timestamp ordering. This code has no application or compositor name checks. It is a local component repair, not an upstream-accepted Wine change.

The preparer installs only the rebuilt `winex11.so` into the qualified Proton Experimental build, after checking the exact version and SHA-256 hashes of its ntdll, win32u and Windows X11 module. It backs up the original as `winex11.so.valve-original-focus`, defers changes while Proton is running or downloading, and restores the original if a partial update retains our module in an unqualified build. Other builds and modified drivers are left alone. A future Proton update needs qualification before this repair is applied to it. The repair applies to every game using that qualified Proton build; there is no AoE2 keyboard rule.

## Validation

The M3 Pro restoration exercised the 4K VM, private GPU driver, x86 Vulkan placed-mapping guard, and the patched FEX signal/SMC regressions. After sign-in and the normal downloads, the real Valve tool was patched and AoE2 reached gameplay at 3024×1964. The general Wine focus repair also passed an injected stale offer in the real game and F10 after Alt-Tab, with no KDE focus rule. Detailed results and the startup driver-discovery fix are in [VALIDATION.md](VALIDATION.md). No new game FPS measurement is claimed.

The same binary release also passed the 4K VM, FEX signal/SMC regressions, placed-mapping guard and 120-frame native Vulkan rendering check on an M1 MacBook Air. M1 validation is recorded separately from the M3 game result.

When the KDE installer is present, guest setup also mounts its idle browser-integration helper over the native host inside the Steam VM. This covers Steam's first bootstrap recreating `htmlcache` and discarding the profile-specific override. The host desktop's browser integration is unaffected.

Run the preparer regression tests on any Linux development machine:

```bash
python3 -m unittest discover -s mac-steam/tests -v
```

The X11 regression uses Wine's actual source functions with the pointer wait stubbed and real X server focus/timestamp handling. It requires a C compiler, Xlib development files and Xvfb. The original function fails the stale-offer case; the patch passes it and the user-switch cancellation cases:

```bash
python3 mac-steam/tests/focus-retry.py /path/to/patched-wine/dlls/winex11.drv/event.c
```

## Rebuilding from source

Build scripts create artifacts; they do not install a graphics stack or reboot a machine. Keep all patches with the scripts. Source commit IDs and submodule commits are pinned; package/toolchain updates can change the resulting binary hashes.

For the M3 kernel, `build/kernel.sh WORK_DIRECTORY` runs makepkg against the
pinned public source and six patches on ARM64. Install the makedepends listed in
`build/kernel/PKGBUILD`; the recipe also prepares its qualified Rust/bindgen
toolchains. Alternatively extract the release's complete kernel source bundle
and run `makepkg --syncdeps` there. `build/repack-kernel.py` records the exact
binary assembly used by this release, retaining the qualified base kernel image
and replacing its display module. `build/kernel-source.sh` creates the complete
source bundle from the pinned base checkout. These build steps are unnecessary
on the machine running the installer.

For FEX on ARM64, install `base-devel clang cmake ninja git python zstd`, then:

```bash
bash mac-steam/build/fex.sh "$HOME/.cache/mac-steam-build"
```

For ARM Mesa, also install `meson llvm libclc spirv-llvm-translator spirv-tools glslang python-mako python-yaml python-packaging python-ply rust-bindgen libdrm wayland wayland-protocols libx11 libxext libxfixes libxshmfence libxxf86vm libxrandr libxcb expat zstd zlib libglvnd`, with a working stable Rust toolchain:

```bash
bash mac-steam/build/mesa-native.sh "$HOME/.cache/mac-steam-build"
```

For both x86 Mesa stacks, run [build/mesa-x86.sh](build/mesa-x86.sh) on an x86-64 Linux machine with Docker. It checks out the same base, applies the five patches, and uses [build/mesa-x86-container.sh](build/mesa-x86-container.sh) inside Arch Linux. The container installs its own build dependencies, including multilib.

`build/overlays.sh X86_STAGE_PARENT OUTPUT_DIRECTORY` combines those staged drivers with the distribution's base overlays and adds Valve's graphics-provider manifest. Images always use 4096-byte blocks.

Build the Wine X11 module on x86-64 Linux with Docker, Git, Python and zstd:

```bash
bash mac-steam/build/wine-focus.sh "$HOME/.cache/mac-steam-wine-build"
```

Only `winex11.so` is installed; the incidental ntdll/win32u build products are not used. Both the binary and complete corresponding source archives are published beside the FEX/Mesa assets. The installer stores that Wine source under `sources/wine-focus`. Wine is LGPL-2.1-or-later; its license and source-file notices are included.

## Recovery

Close Steam/muvm before changing versions. To restore the preceding private installation:

```bash
sudo ln -sfn "$(readlink -f /opt/mac-steam-ultimate/previous)" /opt/mac-steam-ultimate/current.rollback
sudo mv -Tf /opt/mac-steam-ultimate/current.rollback /opt/mac-steam-ultimate/current
```

Steam tool files can be restored from `*.valve-original` and `*.pre-ultimate` after disabling this launcher/preparer. Steam's Verify Integrity operation can also restore its managed files. Keep game saves and library directories in place.

The M3 kernel can be bypassed by selecting the retained `linux-aurora` entry in
Limine. Installer-modified Limine files have `.pre-mac-steam` backups. To undo the
CPU/panel policy, disable `mac-steam-m3-panel.service`, remove
`/etc/modprobe.d/90-mac-steam-m3.conf` and `/etc/tmpfiles.d/mac-steam-m3.conf`, and
restore the desired `halt_poll_ns` value (the tested package default was 500000).
Rolling back the private Steam prefix alone does not remove the kernel or tuning.

The Proton X11 module's original is `winex11.so.valve-original-focus` beside `winex11.so`. Restore it with Steam closed, or verify Proton Experimental in Steam, after disabling the focus preparer if you want to keep Valve's module. Rolling back the private prefix alone does not replace this Steam-library file.

Upstream FEX, Mesa and bundled dependencies retain their own licenses. FEX binaries include bundled dependency license notices; the installer also downloads the full patched Mesa source, including its copyright and license notices, into `sources/mesa` in the private installation. Patches preserve their authorship. This repository packages a local working configuration; it is independent of Valve, FEX, Asahi Linux and Omarchy.
