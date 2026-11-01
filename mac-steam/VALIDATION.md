# Validation — 2026-11-01

## Temporary CPU performance policy — 2026-11-01 late morning

After the FEX server lifetime repair below, the M3 still took 114–119 seconds
to first full-size game presentations. Frequency sampling found that schedutil
frequently left the P-core cluster well below its 4.056 GHz maximum during
initialization. A temporary standard performance governor test reached that
same marker in 73.304 seconds. The original governor was restored afterward.
Reducing FEX's hot-SMC threshold did not improve startup and was reverted.
Diagnostic profiling and sampling are disabled in the candidate installation.

The candidate installer installs native ARM `gamemode 1.8.2-3` and adds the
desktop account to its packaged `gamemode` group. GameMode's complete test suite
passes, including the governor helper, without a new login or password prompt.
The host launcher uses GameMode's native client API around muvm's lifetime,
without injecting a native preload library into FEX or Proton. An unavailable
library or refused request warns and still launches Steam. The request ends on
normal child exit, launch failure, child crash and forwarded termination.
Seven process tests cover these paths; all 25 Steam regression tests and
ShellCheck pass. No FEX/Mesa/Wine/kernel binary changed.

The full candidate installer completed on the M3. A **fresh Steam VM** reached
the first focused **3024×1964** game presentation events in **79.224 seconds**,
versus **118.867 seconds** with the preceding public installer (about 33% less
elapsed time). This is an individual launch comparison, not a guaranteed time.
Both CPU clusters used the performance governor during the candidate launch.
The menu was visually checked, a new skirmish loaded, and F10 opened its in-game
menu. No game integrity check, rendering resolution or quality setting changed.
Normal game and Steam shutdown ended the host request and restored both CPU
clusters to their original `schedutil` governors. A subsequent `--prepare` did
not activate GameMode. A separate finite native-client request also restored
the governors after exit.

Published payload: `2a41e2b6c6f5c2308bc177529c040b1f18c200f0`. Bootstrap
commit `6aa9d38` pins archive SHA-256
`ff6c6c701ed07d9f10dbe9a34be90549a2854e4ac21683683f2c3d24deda778c`.
The anonymous public curl installer completed on the M3. Before running it,
the account's new group membership was removed deliberately; the installer
restored it. Installed launcher hashes match the tested source. A fresh Steam
VM from that installation reached the same full-size marker in **78.120 seconds**;
Spectacle captured the actual intro animation. The two GameMode launches thus
measured 78–79 seconds, compared with the preceding public install's 118.867.
The temporary sleep inhibitor was stopped after measurement. This update has
not been installed or tested on the currently offline M1.

## Fresh Omarchy reinstall — 2026-11-01 morning

The owner reinstalled both Macs. The public KDE, keyboard and Steam curl
installers completed on both from the new OS installations and empty Steam
installer caches. The M1 retained distribution kernel `7.2.11-13-1-ARCH`.
The M3 rebooted into `7.2.11-11-dsc3-ARCH`, boot ID
`580cea91-238f-47c5-8056-7ab17b0efef4`, and started native KDE with password
login. Panel timestamps `Y`, KVM polling `0`, and keyboard parameters `2/1/1`
persisted across that reboot. Post-reboot M1 checks are still pending.

After the owner signed in and downloaded AoE2 on the M3, its apparent launch
failure was inspected while the process was still running. No component was
changed or installed during that attempt. Steam recorded launch at 09:12:34 CET,
the game process at 09:13:32, and a screenshot captured the main menu by about
09:15. The same launch entered a new skirmish and F10 opened its in-game menu.
No game crash dump, guest OOM or new GPU fault was found during this check.

The actual game mapped the private native ARM Vulkan driver and patched Wine
module. The downloaded Valve tool's FEX SHA-256 was `cf4ee475...`; its Wine
X11 module was `27539e89...`, matching the pinned release. The Steam VM had
4096-byte pages and registered `/opt/mac-steam-ultimate/current/fex/bin/FEX`
as its x86-64 interpreter. This establishes a fresh-install M3 gameplay/input
result. It does not establish extended stability or a startup optimization.

The next launch repeated the delay: **192.8 seconds** from Steam IPC to its
first focused 3024×1964 presentation events. Steam's prerequisite checker took
about 55 seconds, and the subsequent game compatibility launch took another
55 seconds before the AoE process appeared. This rules out attributing the whole
delay to one-time setup or game JIT compilation.

Tracing found that pressure-vessel's short FEX helpers repeatedly finish but
leave their output pipes open through a newly spawned server's one-second idle
timeout. The native manager starts a server with a watch pipe; when an existing
server wins the lock, that watch pipe is not attached to it. The manager closes
its connection anyway, allowing the existing server to exit between helpers.
A real, successful tiny x86 program averaged 1.028 seconds when its output was
captured normally and 0.0146 seconds while a server connection was retained.

The packaged manager launcher now retains a connection for pressure-vessel's
lifetime while delegating native startup to the pinned FEX manager. Five process
tests cover existing-server lifetime, readiness/EOF, termination cleanup,
unready/missing servers and the long-library-path temporary-socket fallback.
All 18 Steam tests pass. The full candidate installer completed on the M3.
No missing dependency was reproduced; this fixes a launcher lifetime bug.

The first complete candidate launch produced focused 3024×1964 presentation
events after **113.7 seconds**, versus **192.8 seconds** before the fix. Its
prerequisite and game-launch stages took approximately 23 and 21 seconds,
versus about 55 seconds each previously. This is a single end-to-end comparison,
supported by the isolated helper test; it is not an instantaneous-start claim.
KDE locked during the unattended run, so these events measure game presentation,
not visibility through the lock screen. Normal unlock showed the rendered menu.
That launch subsequently entered a new skirmish; F10 opened the in-game menu.

The repair is published in payload `2b39d57c9535e4db4512f3112102f46f999aa710`;
bootstrap commit `0098743` pins its archive SHA-256
`205b98bedd91ae686a82a5d2efa46c320b5182716f3b29e6755f49863afa19db`.
The anonymous public `curl | bash --user e` installer completed on the M3 and
installed the identical lifetime launcher. After restarting Steam, a repeat
launch reached focused full-size frames in **118.9 seconds**, with the desktop
unlocked. Spectacle captured the actual intro animation. Normal exit of the
preceding candidate game and Steam had left no server/manager processes behind.

## Clean-install packaging update — 2026-11-01

The v0.2.0 installer was exercised on the existing M3 installation, then the
machine was rebooted through its automatically selected kernel entry. This is
an upgrade/reboot test; the owner's upcoming OS reinstall is a separate test.

- Package `linux-aurora-dsc 7.2.11.aurora11-3.1` installed through pacman and the
  normal Omarchy mkinitcpio/Limine/m1n1 hooks. All 2,449 package files are present;
  content and ownership checks pass. Only timestamps of 11 regenerated depmod
  indexes differ from the package metadata.
- The generated UKI was extracted and its display-module SHA-256 checked before
  boot selection: `9029fe79689441fb0ee9ddce60dc6f74903b5fb9f95c58fc8dbe4d4ea24c2328`.
- Boot ID changed from `878fdfb6-1175-4e8c-a088-0a21eea82165` to
  `85a499a2-f5fd-4dd1-90ba-295972ad7403`; kernel release remains
  `7.2.11-11-dsc3-ARCH`. Loaded module build-ID notes match the qualified module.
- Plasma Login Manager displayed the normal password login. After ordinary
  authentication, KDE Plasma started. No autologin configuration was added.
- KVM `halt_poll_ns=0` and the panel timestamp value `Y` survived reboot without
  manual activation. The conditional panel service completed successfully.
- The complete corresponding kernel source bundle contains all base source and
  all six patches. Its offline recipe's 12 input checksums match; all six patches
  apply cleanly. The actual-source retirement regression passes 100,000 native
  swaps plus legacy, external, error and inactive-plane cases; the timestamp
  policy regression passes board/external/default/opt-in cases.
- 13 Steam/preparer/host-setup tests and five KDE integration tests pass. The host
  tests check fresh root arguments, retained fallback entries, absent stock-driver
  parameters, idempotence, and refusal to select an unverified module/boot image.
  ShellCheck passes for the updated installer, bootstraps and new build scripts.
- Both updated public curl bootstraps passed normal-user `--check` on the M3;
  the Steam bootstrap passed the same check on the M1. They pin payload
  `b819bb120d1ab43d8c27231e76e9fade726fc78e`, archive SHA-256
  `5c0a31be06ab885762a4604806273bdbfca7a57c53a73cd2d87f23383fd78a9b`.
- All eight assets are publicly available in v0.2.0. A complete run of the public
  Steam curl installer from an **empty download cache** downloaded and verified
  every asset and completed on the M3. Active prefix:
  `/opt/mac-steam-ultimate/releases/mac-steam-ultimate-wip-v0.2.0-20261101T050929-25086`.
- The normal launch reached the intro, full menu and a new skirmish at the
  existing 6048×3928 stress-test display size. F10 opened the in-game menu.
  Guest PID 1841 mapped the private ARM driver and qualified patched Wine module;
  FEX SHA-256 is the baseline `cf4ee475f303bbda6539b333dda2c34ce2ca8146c1f5deb3f13975b7a8473798`.
  Profiling and measurement hooks were absent. The game and Steam were closed
  normally before the empty-cache installer run; they were not left running.

An earlier automated startup probe reached focused full-size frames in 191.642 s,
sent Space once, and the game exited at 04:51:21. There was no guest OOM or new
game dump. The subsequent launch above allowed the intro to finish naturally.
The first exit's cause is not established; the benchmark's automatic intro-skip
helper is not included in the installer. No startup speedup is claimed.

The qualified FEX/Mesa/Wine baseline is retained. The private FEX exact-validation
candidate, Mesa compression flag, presentation hooks and profiling are excluded
from this release. Long-session OOM investigation is still outstanding; neither
extended stability nor a 120 FPS game result is claimed.

Hardware: Apple M3 Pro, 14-inch MacBook Pro (`apple,j514s`, `apple,t6030`). Host: reinstalled Omarchy/Arch ARM, kernel `7.2.11-11-dsc3-ARCH`, 16384-byte pages. VM: muvm 0.7.0, 4096-byte pages.

The stock ARM Mesa driver in the VM rejected the kernel's `features 0x3e` contract. The patched private driver enumerated **Apple M3 Pro (G15S B1)**, Vulkan 1.4.363, Mesa base `672657e05e`. Guest binfmt showed `/opt/mac-steam-ultimate/current/fex/bin/FEX` as the x86-64 interpreter.

## Checks performed on the reinstalled machine

| Check | Result |
| --- | --- |
| FEX fork: `smc-hot-page` | PASS, hot pages stop faulting; 64 faults for 45,000 stores |
| FEX fork: `smc-same-page` | PASS, including threaded rewrites |
| FEX fork: `smc-restart-state` | PASS |
| FEX fork: `insn-straddle` | PASS, 20,000 fault race with no unexpected target |
| FEX fork: `insn-toolong` | PASS |
| FEX fork: `signal-frame` | PASS |
| Local `smc-invalid.c`, thresholds 0 and 32 | PASS: one SIGILL, correct trap 6 / `ILL_ILLOPN`, repaired code returns 7 |
| Local `smc-append.c`, 1,000 instructions / 100 rewrites | PASS, 0.058 seconds in this run |
| x86 `vkplaced.c` through FEX / patched guest Mesa | `placed=correct guard_changed=0` |
| Native Vulkan rendering, `vkcube --c 120` in the VM | PASS, 120 frames, exit status 0 on the M3 Pro GPU |
| Native ARM Steam client | Bootstrap/update completed; client build 1792618285 reached `WaitingForCredentials` |
| Installer hardware/repository preflight | PASS on M3 Pro; x86 development machine rejected |
| Installer installation and repeat installation | PASS; desktop entry, private versions and rollback links created |
| Public `curl .../install-mac-steam-ultimate-wip.sh \| bash -` | PASS on M3 Pro; pinned payload and a fresh FEX release-asset download verified |
| Public bootstrap `--check` as the desktop user | PASS without sudo |
| Preparer tests | 9 PASS: FEX/native ICD updates, preservation/deferred patching, and qualified Proton focus repair/update handling |
| Shell syntax and ShellCheck 0.11.0 | PASS |

Steam was shut down normally between installer runs. Test launches were muted. The desktop session was locked, so login readiness was checked from Steam's logs. No credentials were entered.

## Scope of the game result

This exact FEX source plus the three local patches, and this Mesa base plus the five local patches, reached the AoE2 DE menu and gameplay before the machine was reinstalled. The previous full-resolution menu measurement was about 58 distinct presented frames per second with VSync on. It was not a verified 120 FPS result.

After the owner signed in and downloaded AoE2, the new installation was tested end to end with game build `26272505`, Proton Experimental `11.0-20261027b` and DXVK `3.1.1-97-ga78a467cadb22be`. Its first launch failed at `CreateDXGIFactory`: the native ARM Vulkan bridge followed pressure-vessel's x86 graphics catalog and tried to load an x86 driver. An x86 helper in the same launch could still enumerate the GPU.

The preparer now installs an ARM ICD manifest pointing at `/run/host/usr/lib/libvulkan_asahi.so` and selects it in the main FEX configuration's `AppOverrides` via `HostEnv`. A probe inside the game's actual pressure-vessel container changed from `vkCreateInstance=-9` to successful enumeration of **Apple M3 Pro**. The real game then created its **3024×1964** swapchain and reached gameplay; the owner confirmed it runs. The real downloaded Valve tool uses the private patched FEX (SHA-256 `cf4ee475f303bbda6539b333dda2c34ce2ca8146c1f5deb3f13975b7a8473798`). No new game FPS measurement is claimed.

Keyboard input initially failed because X11 focus remained on a hidden Steam popup despite the game appearing active. An AoE2-only **Accept focus** rule restored input, and the owner confirmed the physical keyboard worked. This was a workaround and has since been removed.

Further tracing captured the underlying sequence during splash replacement: KWin offered focus at server time `39439889`; Steam changed input focus with CurrentTime up through `39440081`; Wine's delayed request arrived at `39440440`, still carrying `39439889`. X11 rejected it. Normal Alt-Tab, five rapid switching delays and a native globally-active test client all worked, demonstrating why steady-state tests alone missed it.

A local Wine source patch now verifies a timestamped request, obtains a fresh server timestamp if the WM still selects its target, and retries once after checking that selection again. A regression compiling the real Wine functions against Xvfb fails on the original stale-offer case and passes all five cases with the patch, including user switches before/during recovery and absent EWMH support.

The rebuilt `winex11.so` uses Wine revision `7b3ceaf8644bb5d57140903e12897efac69be16a`; SHA-256 is `27539e89604760258a62e003c37de18e2503ee5ec56d5d96127a50cfba3d3276`. In the real AoE2 process, an intentionally stale offer `40839640` was rejected; the patched driver retried at `40839680` and received FocusIn. Simulated F10 opened the in-game menu in a new skirmish and after Alt-Tab. KWin's rule file is empty. Verbose Wine event logging used for diagnosis was removed before these game input checks; the FEX binary hash and native Vulkan setting remain unchanged. No new game FPS result is claimed.

The updated full installer then completed on the M3 using the public Wine binary/source assets, with log `/var/lib/mac-steam-ultimate-focus-install.log`. Both public curl bootstraps passed normal-user `--check` with their pinned source payload. Steam was restarted into a fresh VM. One launch acquired focus and exited at 14:37:42 without a crash dump or OOM event; whether the owner closed it was not confirmed. The following launch reached the menu and a skirmish, remained running through 14:48, and passed F10 again. Its actual environment has `WINEDEBUG=-all`, its mappings contain the patched module, and both host/guest active-Proton guards were checked. This does not establish extended game stability or a new FPS result.

The AoE-only Vulkan bridge is enabled using FEX's Steam application configuration and Arch library paths. Valve supplies the bridge binaries with its FEX tool after sign-in/game installation.

## M1 installation — 2026-10-31

Hardware: MacBook Air M1 (`apple,j313`, `apple,t8103`), 8 GB RAM. Host: Omarchy/Arch ARM, kernel `7.2.11-11-dsc3-ARCH`, 16384-byte pages. The same published FEX and Mesa binaries were installed without rebuilding; the installer now accepts this M1 as well as the M3 Pro.

| Check | Result |
| --- | --- |
| Hardware/repository preflight and installation | PASS for desktop account `e` |
| Private muvm guest | 4096-byte pages, binfmt points to the private FEX |
| Private native Vulkan driver | Apple M1 (G13G B1), Vulkan 1.4.363 |
| Fork SMC/signal checks | All six PASS: hot-page, same-page, restart-state, instruction straddle, instruction length, signal frame |
| Local invalid-opcode regression | PASS at hot-page thresholds 0 and 32 |
| IR append regression | PASS, 1000 instructions / 100 rewrites |
| x86 Vulkan placed mapping through FEX | `placed=correct guard_changed=0` |
| Native Vulkan rendering in the VM | `vkcube --c 120`, PASS, exit status 0 on the M1 GPU |
| Native ARM Steam client | Bootstrap/update completed; client build 1792618285 opened its sign-in window |
| Updated public Steam bootstrap | PASS: normal-user `--check` and complete root rerun using the public curl URL |
| KDE browser helper fallback | Idle helper bound inside the existing Steam VM; host executable checksum unchanged |

These are runtime and graphics checks on the M1. They do not establish an M1 AoE2 game result or frame rate.
