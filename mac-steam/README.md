# Install Mac Steam Ultimate WIP

The native ARM Steam client runs inside **muvm's 4K-page Linux guest** on the Mac's 16K-page host. Windows games use Proton and FEX. The private ARM Mesa stack is bind-mounted over the guest's Mesa libraries during VM startup. The x86 Mesa stacks are 4K EROFS overlays on the Arch FEX rootfs. These mounts belong to the guest kernel.

## Pinned components

| Component | Source/version |
| --- | --- |
| FEX | [StonkGuy/FEX](https://github.com/StonkGuy/FEX/tree/b608a47670de0ce6cca519858c2e57a2590344da), `b608a47670de0ce6cca519858c2e57a2590344da`, from `eac-2610` |
| FEX local fixes | `patches/fex/0002`–`0004`: invalid opcode handling on hot SMC pages, larger hot-page tracking, constant-time IR block append |
| Mesa, ARM64 + x86-64 + i386 | [omacom/mesa](https://github.com/omacom/mesa/tree/672657e05e6b382a0203975f7a26c46f9a674973), `672657e05e6b382a0203975f7a26c46f9a674973` |
| Mesa local fixes | `patches/mesa/0001`–`0005`: M3 G15 virtio wire conversion, queue priority limits, VM status handling, placed mapping bounds, host-backed memory accounting |
| Binary assets | GitHub release `mac-steam-ultimate-wip-v0.1.0`, pinned by [SHA-256](artifacts.sha256) |

FEX is built with Steam support, bundled fmt/xxhash, release optimization and all three local fixes. The tested configuration enables seccomp fidelity and uses `SMCHotPageFaults=32`, reduced x87 precision and no disk code cache. Profiling is disabled for normal use.

The distribution's `FEX-Emu` package remains a muvm prerequisite. **The Steam VM and Valve FEX compatibility tool use the private patched FEX**, rather than that package's older executable. The guest binfmt registration points directly at the private FEX binary.

Steam, Proton, muvm, libkrun, virglrenderer and base rootfs/overlay packages come from configured Omarchy/Asahi repositories or Valve. They continue receiving their normal updates. This release pins our FEX/Mesa sources and binaries, not the entire operating system or proprietary Steam client.

Baseline used on 2026-10-31: native `omarchy/steam 1.0.0.87-1`, client build `1792618285`, `muvm 0.7.0-1`, `libkrun 1.19.7-1`, `virglrenderer 1.3.0-2`, `fex-emu-rootfs-arch 20260318-1`, base Mesa overlays `26.2.3-1`, host `mesa-aurora/vulkan-aurora 26.3.0-devel` at the same Mesa base commit, kernel `7.2.11-11-dsc3-ARCH`.

## Integration

Files live under `/opt/mac-steam-ultimate/releases/`; `current` selects the active installation and `previous` retains the preceding one. Distribution-owned Mesa/FEX executables are preserved on the host. Steam's user desktop entry launches `/usr/local/bin/steam-mac-ultimate`; its previous entry is saved as `steam.desktop.pre-ultimate`. `/usr/local/bin/steam` and `/usr/local/bin/omarchy-launch-steam` route command-line launches, game shortcuts and Omarchy bindings through the same setup; existing local commands are backed up as `*.pre-ultimate`. Inside the 4K guest the wrapper selects `/usr/bin/steam` directly.

Valve's FEX compatibility tool (Steam app `3127680`) supplies the Vulkan guest/host bridge. `runtime/prepare.py` runs before Steam and watches for completed tool downloads while Steam runs. It replaces the four FEX executables atomically and saves the first originals as `*.valve-original`. It defers changes when the tool is downloading or running. Existing JSON settings are merged and backed up as `*.pre-ultimate`.

For AoE2 only (app `813780`, executable `AoE2DE_s.exe`), the preparer adds the Arch library paths missing from the thunk database and enables the native Vulkan bridge through FEX's Steam application configuration. It discovers additional Steam library paths, including paths containing spaces. Other games receive the shared FEX correctness fixes; their Vulkan bridge settings are left to Steam.

No account credentials or game files are bundled. First use requires Steam sign-in and the normal game/runtime downloads. The installer leaves resolution and game graphics settings to the player.

## Validation

The M3 Pro restoration exercised the 4K VM, private GPU driver, x86 Vulkan placed-mapping guard, and the patched FEX signal/SMC regressions. Detailed results are in [VALIDATION.md](VALIDATION.md). AoE2 reached the menu and gameplay with this FEX/Mesa patch set in the preceding installation; the fresh-machine validation distinguishes that history from tests performed after reinstalling.

The same binary release also passed the 4K VM, FEX signal/SMC regressions, placed-mapping guard and 120-frame native Vulkan rendering check on an M1 MacBook Air. M1 validation is recorded separately from the M3 game result.

Run the preparer regression tests on any Linux development machine:

```bash
python3 -m unittest discover -s mac-steam/tests -v
```

## Rebuilding from source

Build scripts create artifacts; they do not install a graphics stack or reboot a machine. Keep all patches with the scripts. Source commit IDs and submodule commits are pinned; package/toolchain updates can change the resulting binary hashes.

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

## Recovery

Close Steam/muvm before changing versions. To restore the preceding private installation:

```bash
sudo ln -sfn "$(readlink -f /opt/mac-steam-ultimate/previous)" /opt/mac-steam-ultimate/current.rollback
sudo mv -Tf /opt/mac-steam-ultimate/current.rollback /opt/mac-steam-ultimate/current
```

Steam tool files can be restored from `*.valve-original` and `*.pre-ultimate` after disabling this launcher/preparer. Steam's Verify Integrity operation can also restore its managed files. Keep game saves and library directories in place.

Upstream FEX, Mesa and bundled dependencies retain their own licenses. FEX binaries include bundled dependency license notices; the installer also downloads the full patched Mesa source, including its copyright and license notices, into `sources/mesa` in the private installation. Patches preserve their authorship. This repository packages a local working configuration; it is independent of Valve, FEX, Asahi Linux and Omarchy.
