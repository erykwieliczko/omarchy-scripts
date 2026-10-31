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
| Preparer tests | 4 PASS: tool updates, deferred patching, settings preservation, library paths with spaces |
| Shell syntax and ShellCheck 0.11.0 | PASS |

Steam was shut down normally between installer runs. Test launches were muted. The desktop session was locked, so login readiness was checked from Steam's logs. No credentials were entered.

## Scope of the game result

This exact FEX source plus the three local patches, and this Mesa base plus the five local patches, reached the AoE2 DE menu and gameplay before the machine was reinstalled. The previous full-resolution menu measurement was about 58 distinct presented frames per second with VSync on. It was not a verified 120 FPS result.

The fresh machine has no signed-in Steam account or downloaded AoE2 game files. A new end-to-end game launch and the preparer's application of the Valve tool after its real download therefore remain for the signed-in session. The preparer's download/update behavior is covered by simulated Steam tool fixtures; FEX and the GPU regressions above ran on the real M3.

The AoE-only Vulkan bridge is enabled using FEX's Steam application configuration and Arch library paths. Valve supplies the bridge binaries with its FEX tool after sign-in/game installation.
