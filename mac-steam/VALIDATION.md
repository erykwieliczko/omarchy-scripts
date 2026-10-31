# Validation — 2026-10-31

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
