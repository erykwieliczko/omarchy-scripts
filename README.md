# Omarchy scripts

## Install Mac Steam Ultimate WIP

Steam on **Omarchy / Arch Linux ARM, Apple M3 Pro (T6030)**, using the FEX and Mesa fixes that got Age of Empires II: Definitive Edition running.

Run this from a terminal in your desktop account:

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-steam-ultimate-wip.sh | bash -
```

The script asks for sudo, downloads a pinned installer and checksum-verified binaries, installs the required packages, and adds **Steam (Mac Ultimate WIP)** to the app launcher. You can also launch it with `steam-mac-ultimate`.

Sign in to Steam normally, install AoE2 DE, and select **Proton Experimental** in the game's Compatibility settings. Steam downloads its FEX compatibility tool automatically. The launcher applies our pinned FEX build when that download completes, including after subsequent tool updates. Exit Steam and reopen it if a tool update happened while a game was running.

The installer is repeatable, keeps backups of replaced Steam files, and supports a root invocation with `--user YOUR_ACCOUNT`. Close existing Steam/muvm applications before installing. A first installation downloads roughly 1 GB before Steam's own client/runtime downloads. Keep at least 6 GiB free, plus space for games.

**WIP scope:** qualified on the 14-inch M3 Pro, Omarchy edge, kernel `7.2.11-11-dsc3-ARCH`. Other Apple chips and distributions are rejected by this release. Game performance depends on the game, Proton, and the host graphics/kernel stack; this installer does not promise 120 FPS.

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
