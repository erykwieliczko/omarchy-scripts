# Omarchy scripts

## Fresh M3 Pro setup for AoE2

Boot your installed Omarchy system, open a terminal as your desktop user, and run:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -
```

Reboot once, log into **Omarchy (KDE Plasma)** with your normal password, and open
**Steam (Mac Ultimate WIP)**. Sign into Steam, install **Age of Empires II:
Definitive Edition**, and play. Steam downloads its compatibility tools normally;
the launcher applies the tested Vulkan and keyboard repairs automatically.

The Steam script installs the qualified M3 display kernel, selects it for the next
boot, enables the panel timestamp fix, and disables costly KVM idle polling.
Everything is downloaded as checksum-verified binaries; installation does not
compile FEX, Mesa, Wine or the kernel. Your resolution and graphics quality remain
your choice. The experimental lossless compression and FEX short-validation
builds are not defaults in this release.

## Install Mac Steam Ultimate WIP

Steam on **Omarchy / Arch Linux ARM, Apple M1 (T8103) or M3 Pro (T6030)**, using the FEX and Mesa fixes that got Age of Empires II: Definitive Edition running on the M3 Pro.

Run this from a terminal in your desktop account:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -
```

The script asks for sudo, downloads a pinned installer and checksum-verified binaries, installs the required packages, and adds **Steam (Mac Ultimate WIP)** to the app launcher. You can also launch it with `steam-mac-ultimate`.

Sign in to Steam normally and install AoE2 DE. The tested native ARM Steam client uses **Proton Experimental** through its FEX compatibility layer. The launcher applies our pinned FEX build when that download completes, including after subsequent tool updates. Exit Steam and reopen it if a tool update happened while a game was running.

The installer is repeatable, keeps backups of replaced Steam files, and supports a root invocation with `--user YOUR_ACCOUNT`. Close existing Steam/muvm applications before installing. A first installation downloads roughly 1 GB before Steam's own client/runtime downloads. Keep at least 6 GiB free, plus space for games.

**WIP scope:** supports the M1 MacBook Air and 14-inch M3 Pro on Omarchy edge. On the M3 Pro the Steam script also installs the qualified `7.2.11-11-dsc3-ARCH` kernel; a prior custom kernel installation is unnecessary. The stock kernel remains available as a boot fallback. Other Apple chips and distributions are rejected by this release. See the validation notes for checks performed on each machine. Extended game stability remains under investigation after a long stress-test menu exhausted guest RAM; this installer does not promise 120 FPS.

See [versions, implementation, validation and rebuilding](mac-steam/README.md).

## Install Mac KDE Ultimate WIP

Use **KDE Plasma as your Omarchy desktop**, with KDE's Plasma Login Manager and a normal password prompt:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
```

This installs the full Plasma package set and desktop apps, selects **Omarchy (KDE Plasma)** for login, imports the current Omarchy palette/wallpaper, and adapts the session's launchers and background services. Existing Hyprland sessions remain available. Packages come from your configured repositories; no compilation is required.

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

Changes take effect immediately and survive reboot, including at the login screen. The script uses the kernel's built-in `hid_apple` settings, saves `/etc/modprobe.d/apple-keyboard.conf`, and runs `mkinitcpio -P` to include the configuration in the boot images. It is independent of KDE or Hyprland and can be run again.

Check support and current settings without changing anything:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/setup-mac-keyboard.sh | bash -s -- --check
```

Each installation backs up the previous configuration, live driver values, and `/boot/initramfs-*.img` files under `/var/lib/omarchy-mac-keyboard/backups/`. If configuration, rebuilding, or live activation fails, the script attempts to restore them automatically. To undo a successful installation, restore `apple-keyboard.conf` from the chosen backup (or remove `/etc/modprobe.d/apple-keyboard.conf` if that backup has no configuration file), run `sudo mkinitcpio -P`, and reboot. The `before-*` files record the previous live values.

Validated on the 14-inch M3 Pro running Omarchy / Arch Linux ARM, kernel `7.2.11-11-dsc3-ARCH`. Other Apple Silicon models require the same three driver parameters; `--check` verifies their availability.
