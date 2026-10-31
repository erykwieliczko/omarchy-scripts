# Install Mac KDE Ultimate WIP

Installs KDE Plasma on an existing Omarchy / Arch Linux ARM installation on Apple Silicon. Qualified on the M3 Pro, kernel `7.2.11-11-dsc3-ARCH`, Plasma/KWin/Plasma Login Manager 6.8.2 and Qt 6.12.0.

The installer uses the distribution's `plasma-meta` package and KDE desktop applications. The [upstream Plasma Login Manager](https://github.com/KDE/plasma-login-manager) provides the password login screen. Automatic login is disabled, including in the old SDDM fallback configuration.

## Usage

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-kde-ultimate-wip.sh | bash -
```

Run from your normal desktop account; the bootstrap invokes sudo. Root can specify `--user ACCOUNT`. `--check` performs platform/account checks without changing the installation. `--activate` schedules the graphical switch after installation and closes the existing desktop session. Save open work before using that option. Without it, the new login manager starts after a reboot.

At login, **Omarchy (KDE Plasma)** is preselected. The native **Plasma (Wayland)** and existing Hyprland sessions are also available. This is a native Plasma session using KWin, Plasma panels, System Settings, its locker, power management and portals.

## Integration fixes

- Keeps Omarchy's Mac display-readiness and first-boot checks on the new login service.
- Clears stale Hyprland/UWSM environment variables and forced GTK/Qt scaling in the Plasma session. KWin manages each display's scale.
- Restricts the Omarchy wallpaper daemon, sleep locker, Bluetooth pairing agent and other Hyprland shell helpers to Hyprland sessions. Plasma supplies the corresponding desktop functions.
- Lets KWin's Fcitx Wayland launcher pass the native input-method socket to Omarchy's supervised Fcitx service. Preserves Omarchy's per-user D-Bus activation configuration and XCompose support.
- Adds a KDE-only `uwsm-app -- COMMAND ...` compatibility launcher for existing Omarchy app helpers. The KDE-specific `omarchy` wrapper handles terminal launch, screen lock and logout; other commands use the existing Omarchy CLI.
- Imports `~/.local/state/omarchy/current/theme/colors.toml` as the KDE `Omarchy` color scheme and applies the current background. A user path unit watches `theme.generation`. `omarchy-kde-sync-theme` also applies a theme manually.
- Overrides KDE browser integration **only inside Steam's CEF profile**. The native helper otherwise spins inside muvm; the Steam-specific manifest points to an idle helper. Ordinary browser profiles retain their KDE integration.

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
- Installer reruns preserve the KDE profile; four integration tests and ShellCheck pass.

Run the portable tests with:

```bash
python3 -m unittest discover -s kde/tests -v
```

Suspend/resume and every Omarchy compositor-specific command are not exhaustively tested by this installer.
