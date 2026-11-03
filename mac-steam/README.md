# Install Mac Steam Ultimate WIP

On the tested M3 Pro, the native ARM Steam client and FEX run **directly on the
16K host with 4K process mappings**. The installer enables Aurora's mixed-page
support with `user4k=on`, rebuilds the boot images, and verifies their embedded
arguments. Reboot once after installation. No kernel compilation is required.

Windows games use Proton and FEX. A root-owned helper prepares a private mount
namespace and drops privileges before starting Steam as your desktop account.
The same private ARM Mesa and x86 EROFS overlays are used in both launch modes;
the desktop's Mesa mounts stay separate. **muvm remains available as a fallback**.
Native FEX is selected automatically when 4 KB process support is active,
without a chip or model allowlist.

## Pinned components

| Component | Source/version |
| --- | --- |
| FEX | [StonkGuy/FEX](https://github.com/StonkGuy/FEX/tree/b608a47670de0ce6cca519858c2e57a2590344da), `b608a47670de0ce6cca519858c2e57a2590344da`, from `eac-2610` |
| FEX fixes | `patches/fex/0002`–`0004`: invalid opcode handling on hot SMC pages, larger hot-page tracking, constant-time IR block append; `0006`: upstream PR 6081 by jgoyvaerts, avoiding duplicate concurrent compilation |
| Mixed-page launcher | Unmodified `tools/aurora-userpages` from `omacom/linux-aurora` `3bdf11d3acb6ea1511b0611ddd40ac5336b7b215`, with corresponding source in its archive |
| Mesa, ARM64 + x86-64 + i386 | [omacom/mesa](https://github.com/omacom/mesa/tree/a19691114759e2c0507f3502cf6166ef2c6e2e33), `a19691114759e2c0507f3502cf6166ef2c6e2e33` |
| Mesa local fixes | `patches/mesa/0001`–`0005`: M3 G15 virtio wire conversion, queue priority limits, VM status handling, placed mapping bounds, host-backed memory accounting; `0006`–`0007`: Satisfactory disabled-depth-bounds state at draw and pipeline creation |
| Wine focus repair | `ValveSoftware/wine` `7b3ceaf8644bb5d57140903e12897efac69be16a` + `patches/wine/0001`, qualified for Proton Experimental `11.0-20261027b` |
| M3 kernel | `omacom/linux-aurora` `3bdf11d3acb6ea1511b0611ddd40ac5336b7b215`, package `linux-aurora-dsc 7.2.11.aurora11-3.1`, kernel release `7.2.11-11-dsc3-ARCH` |
| M3 kernel fixes | DSC sequencing, display/audio hold-link, Wi-Fi country map, native framebuffer retirement, optional T6030 swap timestamps |
| Custom Steam stack | x86 Proton Experimental `11.0-20261027b`, patched FEX, X11 focus repair and Steam Runtime `4.0.20261021.265997`, bundled in `mac-steam-ultimate-wip-v0.4.0` |
| Binary assets | Mesa is from `v0.5.0`, the stack from `v0.4.0`, FEX r2 and userpages from `v0.3.0`, and the kernel/Wine components from `v0.2.0`, all pinned by [SHA-256](artifacts.sha256) |

FEX is built with Steam support, bundled fmt/xxhash, release optimization, all
three local fixes and upstream PR 6081. The tested configuration enables seccomp
fidelity and uses `SMCHotPageFaults=32`, reduced x87 precision and no disk code
cache. Profiling is disabled for normal use.

The distribution's `FEX-Emu` package remains installed for its integration files
and the muvm fallback. **Both launch paths and Valve's FEX compatibility tool use
the private patched FEX**. Native mode adds two temporary binfmt registrations;
they are removed when Steam exits. Existing distribution registrations remain.

Steam, muvm, libkrun, virglrenderer and base rootfs/overlay packages come from configured Omarchy/Asahi repositories or Valve and continue receiving their normal updates. The custom Steam option additionally pins its own copies of Proton, FEX and Steam Runtime; Valve's separate Proton installations retain their normal update behavior. The operating system and proprietary Steam client are not pinned.

System dependencies use a temporary official Arch Linux ARM `CacheServer` for
base ARM repositories mirrored by Omarchy, covering missing mirror files.
Pacman retains the existing database sources, repository priority and signature
policy. Full system upgrades stay in Omarchy's updater.

Baseline used on 2026-10-31: native `omarchy/steam 1.0.0.87-1`, client build `1792618285`, `muvm 0.7.0-1`, `libkrun 1.19.7-1`, `virglrenderer 1.3.0-2`, `fex-emu-rootfs-arch 20260318-1`, base Mesa overlays `26.2.3-1`, host `mesa-aurora/vulkan-aurora 26.3.0-devel` at Mesa base `672657e05e6b`, kernel `7.2.11-11-dsc3-ARCH`.

## Integration

### Custom Proton option

The installer downloads a checksum-pinned, prebuilt stack and registers **Mac
Steam Ultimate (FEX + Proton 11)** under Steam's
`compatibilitytools.d/mac-steam-ultimate/`, including before a user's first Steam
launch. It contains x86 Proton/Wine with the verified X11 focus repair, our FEX
binaries, the native Vulkan bridge, and Steam Runtime 4. No separate Valve tool
download is needed. Files are copied with reflinks when available, never
hardlinked to the system installation. Valve's shipped default prefix template
is retained because Proton needs its DirectX DLL links; player prefixes,
per-user settings and runtime deployment logs are excluded from the release.

The option is selected as the initial global default. An existing AoE2 selection
of x86 Proton Experimental follows the new entry; other explicitly chosen game
tools are preserved. Configuration writes occur while Steam is stopped, with a
`config/config.vdf.pre-mac-stack` backup. A minimal initial config is created when
Steam has not been launched yet. Later manual choices are respected. The entry
can also be selected per game in Properties → Compatibility.

The internal identifier is `mac_steam_ultimate_proton`. Steam's Windows
AutoCloud mapping requires `proton` in this identifier, even when the tool's
manifest already declares its Proton layer. Older registrations and their
existing selections are migrated while Steam is stopped, with backups and
without changing other compatibility choices. The prebuilt v0.4.0 bundle is
repaired during registration; its binaries and prefixes remain in place.
This fixed Satisfactory reporting successful sync while skipping every cloud
save because it could not resolve the Windows save path. The M3 subsequently
downloaded all 11 existing saves.

Satisfactory's default DirectX 12 renderer currently crashes during resource
creation on this stack (`E_INVALIDARG`). Adding `-dx11` in its Steam
Properties → General → Launch Options reached the main menu on the M3.
[Coffee Stain's support page](https://www.satisfactorygame.com/support/) documents
this renderer override. This verifies startup, not extended gameplay.

For an existing AoE2 ARM64 prefix, the preparer retains the complete original as
`813780.arm64-before-mac-stack-TIMESTAMP`, copies Games/Documents/Saved Games and
FEX configuration into a clean x86 compatibility directory, and lets Proton and
Steam run first-use setup. This prevents incompatible ARM64 VC++ libraries from
being carried into x86 Wine. Existing x86 prefixes remain in place. A failed save
copy restores the original directory.

Versions and source provenance are recorded in `stack.json`; Valve tool updates
do not replace the bundle. A new bundled build is installed only while Steam is
stopped, retaining the prior tool outside `compatibilitytools.d` so it cannot
register a duplicate entry. The preparer can still build a local stack from
installed Steam tools when no prebuilt bundle is supplied, after checking the
qualified Proton version and companion hashes.

On an existing Ultimate installation, use the normal public bootstrap with
`--steam-option-only` to update this option, private ARM/x86 graphics and launcher integration without
changing packages, kernel modules or boot configuration. The full command still
performs the normal complete setup for a fresh system.

The M3's Steam Settings page confirms the default. The real custom-tool launch
loaded the bundled FEX executable, 126 bundled Wine modules and native Vulkan
bridge, with no Wine modules from Valve's separate Proton directory. The original
ARM64EC freeze remains unisolated between Wine, FEX and its surrounding userland.
The x86 setup passed one 10-minute-menu/15-minute-skirmish run and a second healthy
26-minute launch before extended gameplay checks ended at the owner's request.

### Launcher and runtime preparation

`steam-mac-ultimate` selects native FEX automatically with working mixed
pages. `steam-mac-ultimate --muvm` explicitly selects the VM, and `--native`
requires native mode. Close Steam and its games before switching. If native
support is unavailable, automatic mode uses muvm. Native mode does not require
sudo or a password prompt from the active local desktop account: a narrowly
scoped Polkit rule permits only the installed root-owned setup helper. Steam,
FEX, Proton and the preparer run as the desktop account.

Files live under `/opt/mac-steam-ultimate/releases/`; `current` selects the active installation and `previous` retains the preceding one. Distribution-owned Mesa/FEX executables are preserved on the host. Steam's user desktop entry launches `/usr/local/bin/steam-mac-ultimate`; its previous entry is saved as `steam.desktop.pre-ultimate`. `/usr/local/bin/steam` and `/usr/local/bin/omarchy-launch-steam` route command-line launches, game shortcuts and Omarchy bindings through the same setup; existing local commands are backed up as `*.pre-ultimate`. Inside an existing 4K launch environment the wrapper selects `/usr/bin/steam` directly.

The installer also installs native ARM GameMode and adds the desktop account to
its standard `gamemode` group. The host launcher holds a GameMode request while
Steam runs, allowing the CPU's performance governor during gaming. This
uses more power while Steam is open. The request ends when Steam exits;
GameMode restores the previous governors when its last client exits.
User GameMode settings remain in effect. A native Python
client owns the request and waits for Steam or muvm; it does not inject `LD_PRELOAD`
libraries into FEX or Proton. Unavailable GameMode produces a warning
and Steam still starts. `--prepare` does not request GameMode.

Valve's FEX compatibility tool (Steam app `3127680`) supplies the Vulkan guest/host bridge. `runtime/prepare.py` runs before Steam and watches for completed tool downloads while Steam runs. It installs the three pinned FEX executables and a server-manager launcher atomically, saving the first originals as `*.valve-original`. It defers changes when the tool is downloading or running. Existing JSON settings are merged and backed up as `*.pre-ultimate`.

The server-manager launcher runs the pinned native manager and holds one server
connection until pressure-vessel closes its lifetime pipe. The pinned manager's
watch pipe is ineffective if a server was already running when it started.
Without a retained connection, short graphics/platform probes repeatedly start
servers that keep their output pipes open until a one-second idle timeout.
This repair keeps the existing server alive for the container and releases the
connection during normal exit or termination. It applies to Steam's prerequisite
checker and game launches; it does not skip prerequisite checks or change FEX's
CPU emulation. Python is already an installed dependency; no compilation is needed.

For AoE2 only (app `813780`, executable `AoE2DE_s.exe`), the preparer adds the Arch library paths missing from the thunk database and enables the native Vulkan bridge through FEX's Steam application configuration. It discovers additional Steam library paths, including paths containing spaces. Other games receive the shared FEX correctness fixes; their Vulkan bridge settings are left to Steam.

After AoE2 finishes downloading, the preparer also supplies
`dxgi.maxFrameLatency = 1` in the game's `dxvk.conf`. This limits render-ahead
for responsive input. Existing explicit latency settings, including `0` for
the application/default behavior, are respected. Other configuration content is
preserved and backed up before adding the default; symlinked configurations
are left to their owner. The watcher handles games installed after Steam setup
and games in additional libraries.

Enable **V-Sync** in AoE2's advanced Graphics options for the tested mouse/pacing
setup. This is a recommendation; the installer leaves your game preferences in
place. On the M3, the player reported noticeably better cursor response with
V-Sync, then a very smooth cursor after the one-frame limit. Passive presentation
measurements were about 102 FPS in both one-frame and V-Sync-only small-skirmish
runs at 3024×1964 using the player's existing Low preset. Capture counters alone
do not measure physical input-to-photon latency or establish a GPU utilization
percentage. See [validation](VALIDATION.md) for the limits of this comparison.

AoE2's native bridge also needs an ARM driver manifest inside pressure-vessel. Its default graphics provider describes the x86 Mesa overlays, so an ARM loader following that catalog cannot load the driver. The preparer writes `FEX-Emu/asahi-native.json`, pointing at the private guest driver exported at `/run/host/usr/lib/libvulkan_asahi.so`. A `ConfigTemplate.json` application override selects it with FEX's `HostEnv` for `AoE2DE_s.exe`; Valve expands the tool-path placeholder into each game's configuration. The manifest and override are restored after tool updates. Driver selection is separate from the x86 overlays, which remain installed.

No account credentials or game files are bundled. First use requires Steam sign-in and the normal game/runtime downloads. The installer leaves resolution and game graphics settings to the player.

The native comparison reached full-resolution intro frames in 26.1–26.2 seconds,
versus 67–77 seconds through muvm with the same qualified FEX. The installed
native launcher with the new PR 6081 build reached that marker in 26.5 seconds.
These are observed launches, not guaranteed startup times or an isolated PR 6081
speedup. First use also downloads runtimes and runs prerequisites. No game
integrity checks, resolution or graphics settings were changed.

The comparison used about 12.1 GiB of whole-machine memory in the menu, versus
14.5 GiB with muvm. This does **not** meet the under-8GB target. The separate
allocator cleanup, strict-zero-ahead DXVK build and constrained-RAM experiments
are not installed; their combined candidate crashed and remains unqualified.

### Clean-install M3 display and CPU setup

The 14-inch M3 Pro (`apple,j514s`) with Omarchy Limine no longer needs the previous machine's custom
build directory. The installer downloads the qualified complete kernel package
and corresponding source, installs it with pacman, checks the generated UKI's
embedded display-module checksum, and selects the new Limine entry. Existing
machine-specific root/encryption arguments are generated by Omarchy's normal
hooks and preserved. The distribution kernel remains installed as a fallback.
Reboot once after installing both KDE and Steam. Other models or boot setups
retain their current kernel and can install the rest of the stack normally.

The installer checks the selected kernel's embedded configuration for mixed-page
support. On supported Aurora builds it adds `user4k=on` to
`GRUB_CMDLINE_LINUX` in `/etc/default/grub`, removes conflicting page switches
from the default arguments, and runs `limine-mkinitcpio`. Omarchy derives Limine's
arguments from that source during later rebuilds, so the option persists.
Every generated UKI is checked for the switch. A failed build or stale command
line restores the previous configuration and boot images from
`/var/lib/mac-steam-ultimate/boot-backups/`. Unsupported kernels keep the muvm
path; the installer does not compile a replacement to obtain mixed pages.

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
120 FPS claim. Other models skip these display-kernel and tuning assets.

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

The v0.5.0 Mesa update fixes Satisfactory Vulkan menu startup with two scoped
depth-bounds workarounds. Vulkan measured about 6.4 FPS versus the earlier DX11
9 FPS baseline at 3024×1964, but still has incorrect lighting; DX11 is the tested
launch setting. This does not qualify Vulkan gameplay. See [VALIDATION.md](VALIDATION.md).

The M3 Pro restoration exercised the 4K VM, private GPU driver, x86 Vulkan placed-mapping guard, and the patched FEX signal/SMC regressions. After sign-in and the normal downloads, the real Valve tool was patched and AoE2 reached gameplay at 3024×1964. The general Wine focus repair also passed an injected stale offer in the real game and F10 after Alt-Tab, with no KDE focus rule. Detailed results and the startup driver-discovery fix are in [VALIDATION.md](VALIDATION.md). No new game FPS measurement is claimed.

The preceding r1 binary release passed the 4K VM, FEX signal/SMC regressions,
placed-mapping guard and 120-frame native Vulkan rendering check on an M1
MacBook Air. The new r2 build and native Steam have also been checked on the M1;
AoE2 gameplay with native FEX on the M1 remains unverified. M1 validation is
separate from the M3 game result.

When the KDE installer is present, both launch paths also mount its idle
browser-integration helper over the native host inside the Steam namespace.
This covers Steam's first bootstrap recreating `htmlcache` and discarding the
profile-specific override. The host desktop's browser integration is unaffected.

Run the preparer regression tests on any Linux development machine:

```bash
python3 -m unittest discover -s mac-steam/tests -v
```

The X11 regression uses Wine's actual source functions with the pointer wait stubbed and real X server focus/timestamp handling. It requires a C compiler, Xlib development files and Xvfb. The original function fails the stale-offer case; the patch passes it and the user-switch cancellation cases:

```bash
python3 mac-steam/tests/focus-retry.py /path/to/patched-wine/dlls/winex11.drv/event.c
```

## Rebuilding from source

The complete Steam option can be packaged on the build machine from the qualified
Steam tool downloads and the installed private component binaries:

```bash
python3 mac-steam/build/compat-stack.py \
  --steam-root "$HOME/.local/share/Steam" \
  --component-prefix /opt/mac-steam-ultimate/current \
  --output /tmp/mac-steam-stack-11.0-20261027b-r1-aarch64.tar.zst
```

This copies only tool distributions, retains required Proton template data, adds
the patched components and source/license notices, removes deployment state and
records provenance. The resulting release archive is installed directly; users
do not compile or construct their own stack.


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

The source recipe now also applies [FEX PR 6081](https://github.com/FEX-Emu/FEX/pull/6081)
as `patches/fex/0006`, imported unchanged from jgoyvaerts's commit
`61663da5bc8391130e4d3fdf0797f0ff9fe44161`. Original authorship, commit message and
the upstream regression test are preserved; see [patch provenance](patches/fex/README.md).
The installer downloads the **r2** binary containing that original patch and
`0002`–`0004`, with attribution in `SOURCE.txt` and the original patch files in
the archive. The separate experimental allocator patch is not included.

Build the page-size launcher on ARM64 (or set `CC=aarch64-linux-gnu-gcc` on x86):

```bash
bash mac-steam/build/userpages.sh /path/to/linux-aurora /path/to/output
```

It extracts unmodified launcher sources and the matching private prctl header
from the pinned kernel commit, builds once, and includes the complete launcher
source and license notices with the binary. End-user installation downloads it.

For ARM Mesa, also install `meson llvm libclc spirv-llvm-translator spirv-tools glslang python-mako python-yaml python-packaging python-ply rust-bindgen libdrm wayland wayland-protocols libx11 libxext libxfixes libxshmfence libxxf86vm libxrandr libxcb expat zstd zlib libglvnd`, with a working stable Rust toolchain:

```bash
bash mac-steam/build/mesa-native.sh "$HOME/.cache/mac-steam-build"
```

For both x86 Mesa stacks, run [build/mesa-x86.sh](build/mesa-x86.sh) on an x86-64 Linux machine with Docker. It checks out the same base, applies the seven patches, and uses [build/mesa-x86-container.sh](build/mesa-x86-container.sh) inside Arch Linux. The container installs its own build dependencies, including multilib.

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

To undo the render-ahead default, set `dxgi.maxFrameLatency = 0` in
`steamapps/common/AoE2DE/dxvk.conf`; the preparer respects that explicit choice.

To disable native mode, launch with `--muvm`. To remove the page-size boot option,
remove `user4k=on` from `/etc/default/grub`, run `sudo limine-mkinitcpio`, and
reboot. That switch is independent of the private Steam prefix. To revoke the
native helper authorization, remove `/etc/polkit-1/rules.d/49-mac-steam-native.rules`.

The M3 kernel can be bypassed by selecting the retained `linux-aurora` entry in
Limine. Installer-modified Limine files have `.pre-mac-steam` backups. To undo the
CPU/panel policy, disable `mac-steam-m3-panel.service`, remove
`/etc/modprobe.d/90-mac-steam-m3.conf` and `/etc/tmpfiles.d/mac-steam-m3.conf`, and
restore the desired `halt_poll_ns` value (the tested package default was 500000).
Rolling back the private Steam prefix alone does not remove the kernel or tuning.

The Proton X11 module's original is `winex11.so.valve-original-focus` beside `winex11.so`. Restore it with Steam closed, or verify Proton Experimental in Steam, after disabling the focus preparer if you want to keep Valve's module. Rolling back the private prefix alone does not replace this Steam-library file.

Upstream FEX, Mesa and bundled dependencies retain their own licenses. FEX binaries include bundled dependency license notices; the installer also downloads the full patched Mesa source, including its copyright and license notices, into `sources/mesa` in the private installation. Patches preserve their authorship. This repository packages a local working configuration; it is independent of Valve, FEX, Asahi Linux and Omarchy.
