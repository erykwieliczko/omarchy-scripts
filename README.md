# Omarchy scripts

## Fresh Mac setup for AoE2

Boot your installed Omarchy system, open a terminal as your desktop user, and run:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -
```

Reboot once, log into **Omarchy (KDE Plasma)** with your normal password, and open
**Steam (Mac Ultimate WIP)**. Sign into Steam, install **Age of Empires II:
Definitive Edition**, and play. Steam downloads its compatibility tools normally;
the launcher applies the tested Vulkan and keyboard repairs automatically.

After runtime setup, the native M3 test reached AoE2's intro in about 26.5 seconds.
First use also downloads Steam's compatibility tools and runs prerequisite
installers; watch Steam's setup progress before retrying.

The keyboard script applies the PC modifier/F-key layout described below.
The KDE and Steam installers use an official Arch Linux ARM package cache to
cover missing files in Omarchy's ARM mirror. Repository metadata, package order
and signature checks stay under Omarchy's configuration.

The Steam script installs the qualified M3 display kernel, selects it for the next
boot, enables the panel timestamp fix, and disables costly KVM idle polling.
It also enables `user4k=on` in the persistent boot configuration and verifies the
rebuilt boot images. With working mixed-page support, Steam uses **native FEX with 4KB process pages**
on the 16KB host; `steam-mac-ultimate --muvm` keeps the VM fallback available.
Everything is downloaded as checksum-verified binaries; installation does not
compile FEX, Mesa, Wine or the kernel. Your resolution and graphics quality remain
your choice. The experimental lossless compression and FEX short-validation
builds are not defaults in this release.

## Install Mac Steam Ultimate WIP

Steam on **Omarchy / Arch Linux ARM with Apple Silicon graphics**, using the FEX and Mesa fixes that got Age of Empires II: Definitive Edition running on the M3 Pro. Installation and backend selection use dependencies and working page-size support, without a chip or model allowlist.

Run this from a terminal in your desktop account:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -
```

The script asks for sudo, downloads a pinned installer and checksum-verified binaries, installs the required packages, and adds **Steam (Mac Ultimate WIP)** to the app launcher. You can also launch it with `steam-mac-ultimate`.

Sign in to Steam normally and install AoE2 DE. The tested native ARM Steam client uses **Proton Experimental** through its FEX compatibility layer. The launcher applies our pinned FEX build when that download completes, including after subsequent tool updates. Exit Steam and reopen it if a tool update happened while a game was running.

The installer is repeatable, keeps backups of replaced Steam files, and supports a root invocation with `--user YOUR_ACCOUNT`. Close existing Steam/muvm applications before installing. A first installation downloads roughly 1 GB before Steam's own client/runtime downloads. Keep at least 6 GiB free, plus space for games.

GameMode requests the performance CPU governor while Steam runs in either mode,
then restores the previous governors on exit.
This uses more power while Steam is open. The native M3 installer test reached
AoE2's full-resolution intro in about 26.5 seconds; first-use setup can take longer.

AoE2 also gets a one-frame render-ahead limit after its download completes,
while existing explicit settings are respected. Enable **V-Sync** in the game's
advanced Graphics options for the tested responsive-cursor setup.

**WIP testing:** the M1 MacBook Air and 14-inch M3 Pro have been tested on Omarchy edge; other models can install the same stack when its dependencies are available. On the 14-inch M3 Pro with Omarchy Limine, the Steam script also installs the qualified `7.2.11-11-dsc3-ARCH` kernel. Other hardware and boot setups retain their existing kernel. The stock kernel remains available as a boot fallback. See the validation notes for checks performed on each machine. Extended game stability remains under investigation after a long stress-test menu exhausted guest RAM; this installer does not promise 120 FPS.

See [versions, implementation, validation and rebuilding](mac-steam/README.md).

## Install Mac KDE Ultimate WIP

Use **KDE Plasma as your Omarchy desktop**, with KDE's Plasma Login Manager and a normal password prompt:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
```

This installs the full Plasma package set and desktop apps, selects **Omarchy (KDE Plasma)** for login, imports the current Omarchy palette/wallpaper, and adapts the session's launchers and background services. Existing Hyprland sessions remain available. Packages come from your configured repositories; no compilation is required. It requires Omarchy and Arch packages, with no CPU architecture or Mac model check.

Reboot after installing. To switch immediately after installation, closing the current graphical session:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -s -- --activate
```

See [KDE integration, backups and validation](kde/README.md).

## Set up Mac keyboard

Make the built-in Apple keyboard behave like a PC keyboard on **Omarchy / Arch Linux ARM, Apple Silicon**:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -
```

The script asks for sudo and applies all three settings:

- **Option ↔ Command on both sides:** Option becomes Super; Command becomes Alt, with right Command acting as right Alt / AltGr.
- **F1–F12 by default:** press F11 alone to send F11.
- **Fn ↔ left Ctrl:** the physical Fn key becomes Ctrl, and the physical left Ctrl key becomes Fn. Hold **physical left Ctrl** with the top row for volume, brightness, and media controls.

Changes take effect immediately and survive reboot, including at the login screen. The script checks the actual `hid_apple` parameters and boot tools, with no machine, CPU or Omarchy identity check, and saves `/etc/modprobe.d/apple-keyboard.conf`. On Omarchy's active Limine setup it uses `limine-mkinitcpio` and verifies that every installed kernel's generated UKI contains the configuration. Other boot setups use `mkinitcpio -P`. It is independent of KDE or Hyprland and can be run again.

Check support and current settings without changing anything:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -s -- --check
```

Each installation backs up the previous configuration, live driver values, raw initramfs files, and (when active) Limine's UKIs and boot configuration under `/var/lib/omarchy-mac-keyboard/backups/`. Boot artifacts retain their full paths under each backup's `boot-files/`; `boot-files.list` records them. If configuration, rebuilding, verification, or live activation fails, the script attempts to restore them automatically. To undo a successful installation, restore `apple-keyboard.conf` from the chosen backup (or remove `/etc/modprobe.d/apple-keyboard.conf` if that backup has no configuration file), rebuild with `sudo limine-mkinitcpio` on Limine or `sudo mkinitcpio -P` otherwise, and reboot. The `before-*` files record the previous live values.

Validated on both a fresh M1 MacBook Air and a 14-inch M3 Pro running Omarchy / Arch Linux ARM, kernel `7.2.11-13-1-ARCH`, including the generated UKI contents. The previous raw-initramfs-only script left the active UKI unchanged; the Limine frontend fixes that persistence bug. Tests cover driver-based detection, installation, piped sudo, conflicts, failed rebuilds, stale UKIs and restoration of the boot configuration. `--check` verifies the required driver parameters and commands.
