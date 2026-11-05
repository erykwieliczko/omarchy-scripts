# Install Mac KDE Ultimate WIP

Installs KDE Plasma on an existing Omarchy / Arch Linux ARM installation on Apple Silicon. Qualified on the M3 Pro, kernel `7.2.11-11-dsc3-ARCH`, Plasma/KWin/Plasma Login Manager 6.8.2 and Qt 6.12.0.

The installer uses the distribution's `plasma-meta` package and KDE desktop applications. The [upstream Plasma Login Manager](https://github.com/KDE/plasma-login-manager) provides the password login screen. Automatic login is disabled, including in the old SDDM fallback configuration.

Package installation uses a temporary official Arch Linux ARM `CacheServer` for
base ARM repositories mirrored by Omarchy. Pacman checks those package copies
against the existing repository hashes and signatures; databases and repository
priority remain unchanged. Full system upgrades stay in Omarchy's updater.
This fixed a fresh M1/M3 installation where Omarchy's live `extra` database
advertised `onetbb-2023.2.0-1` but its mirror returned 404. The official cache
served the matching package and both KDE installations completed.

## Usage

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
```

Run from your normal desktop account; the bootstrap invokes sudo. Root can specify `--user ACCOUNT`. `--check` performs platform/account checks without changing the installation. `--activate` schedules the graphical switch after installation and closes the existing desktop session. Save open work before using that option. Without it, the new login manager starts after a reboot.

At login, **Omarchy (KDE Plasma)** is preselected. The native **Plasma (Wayland)** and existing Hyprland sessions are also available. This is a native Plasma session using KWin, Plasma panels, System Settings, its locker, power management and portals.

## Integration fixes

- Keeps Omarchy's Mac display-readiness and first-boot checks on the new login service.
- Stops other login managers individually when switching desktops, so a missing
  SDDM or greetd unit cannot leave GDM running alongside Plasma Login Manager.
- Clears stale Hyprland/UWSM environment variables and forced GTK/Qt scaling in the Plasma session. KWin manages each display's scale.
- Restricts the Omarchy wallpaper daemon, sleep locker, Bluetooth pairing agent and other Hyprland shell helpers to Hyprland sessions. Plasma supplies the corresponding desktop functions.
- Lets KWin's Fcitx Wayland launcher pass the native input-method socket to Omarchy's supervised Fcitx service. Preserves Omarchy's per-user D-Bus activation configuration and XCompose support.
- Clears forced GTK/Qt/SDL input modules in KDE, including after Plasma reloads the systemd user environment. Native Wayland input remains active; `XMODIFIERS` retains XWayland support. This prevents the Fcitx Wayland Diagnose popup caused by conflicting toolkit modules. See [Fcitx's KDE setup guidance](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland#KDE_Plasma).
- Adds a KDE-only `uwsm-app -- COMMAND ...` compatibility launcher for existing Omarchy app helpers. The KDE-specific `omarchy` wrapper handles terminal launch, screen lock and logout; other commands use the existing Omarchy CLI.
- Imports `~/.local/state/omarchy/current/theme/colors.toml` as the KDE `Omarchy` color scheme and applies the current background. A user path unit watches `theme.generation`. `omarchy-kde-sync-theme` also applies a theme manually.
- Overrides KDE browser integration inside Steam's CEF profile. The native helper otherwise spins inside muvm; the Steam-specific manifest points to an idle helper. The Steam installer also mounts that idle helper over the native executable inside its VM, covering the first client bootstrap recreating the profile. Ordinary host browsers retain their KDE integration.
- Once the updated Steam installer is present, removes the temporary AoE2-only **Accept focus** workaround from earlier installer revisions, preserving other window rules and a backup. The Steam installer now supplies a general Wine fix for timestamp-rejected focus requests. KDE and its normal focus policy remain in control.

Hyprland compositor commands and its shell widgets remain specific to Hyprland. This installer does not port those widgets to Plasma. Omarchy applications, package management and CLI remain installed. User KDE choices are preserved on installer reruns; the initial color scheme and session defaults are applied once.

The Steam/FEX installer is separate and composes with this installer. VM detection accounts for libkrun renaming muvm's process title to `libkrun VM`; activation can still shut Steam down normally before ending the old desktop session.

## Files and recovery

Runtime helpers live in `/usr/local/lib/omarchy-kde`. The session entry is `/usr/local/share/wayland-sessions/omarchy-plasma.desktop`. Plasma Login Manager uses `/etc/plasmalogin.conf`; `/etc/systemd/system/display-manager.service` selects `plasmalogin.service`.

System configuration snapshots are saved under `/var/lib/omarchy-kde/backups/TIMESTAMP-PID/`. Existing user configuration is backed up as `*.pre-omarchy-kde` before the first change. User integration state is in `~/.local/state/omarchy-kde/`.

To return to the previous login manager, from a terminal or SSH:

```bash
sudo systemctl disable plasmalogin.service
sudo systemctl enable --force sddm.service
```

Then reboot, or restart the login manager after saving open work. The SDDM fallback remains configured for password login. Select the Omarchy/Hyprland session there to return to the previous desktop.

## Validation on the M3 Pro

- The owner signed in successfully using the password prompt; the selected session started native Plasma Wayland.
- KWin reports the DRM backend, OpenGL ES 3.2 and **Apple M3 Pro (G15S B1)** hardware rendering.
- The internal panel runs at **3024×1964, 120 Hz**, with KDE-managed desktop scaling. This is the display mode, not a claim about game frame rate.
- Plasma, its authentication agent, PowerDevil, KDE portals and the Omarchy theme watcher start. The user manager has no failed units.
- Spectacle captured the real desktop; the Omarchy wallpaper and palette applied successfully.
- Fcitx's self-diagnostic reports **Wayland native input method protocol: 1** after the KWin launcher fix.
- Steam launches through the existing muvm/FEX setup. Its previously busy Plasma browser integration host was replaced by an idle Steam-only helper.
- Installer reruns preserve the KDE profile; five integration tests pass. The original shell launchers also passed ShellCheck.
- The public `curl | bash` entry point passed both its normal-user `--check` and a full root rerun. The existing KDE session and Steam VM remained running throughout the rerun without `--activate`.
- AoE2 keyboard input was initially restored by a game-specific focus rule. Further tracing reproduced a Steam/Wine timestamp race, and that workaround was retired. The patched Wine driver acquired focus during a deliberately stale offer in the real game; F10 opened the in-game menu, including after Alt-Tab, with an empty `kwinrulesrc`.

Run the portable tests with:

```bash
python3 -m unittest discover -s kde/tests -v
```

Suspend/resume and every Omarchy compositor-specific command are not exhaustively tested by this installer.

## M1 installation

The public curl installer also completed on the M1 MacBook Air (`apple,j313`, `apple,t8103`), kernel `7.2.11-11-dsc3-ARCH`, on 2026-10-31. Plasma Login Manager is enabled, autologin is disabled, and the owner signed into **Omarchy (KDE Plasma)** successfully. KWin reports Apple M1 (G13G B1) hardware rendering with OpenGL ES 3.2, and the user manager has no failed units. The Steam/FEX installer and its M1 runtime/GPU checks also passed.

The owner's Fcitx warning exposed a Plasma environment-import detail: unsetting a variable in a sourced script does not clear an inherited value in Plasma's environment overlay. The session now exports empty GTK/Qt/SDL input-module defaults and explicitly synchronizes them into D-Bus/systemd. The real Plasma `sourceenv` round trip and a user-manager reload retain those empty values. After restarting input through KWin's launcher, Fcitx reports native Wayland protocol 1 with no forced GTK/Qt modules. The warning was fixed through configuration; its notification settings were not disabled.
