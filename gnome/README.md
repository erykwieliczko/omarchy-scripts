# Install Mac GNOME Ultimate WIP

Install standard GNOME, its desktop apps, and GDM password login on an existing
Omarchy installation with Arch packages. There is no Mac model or CPU allowlist.

```bash
curl -fsSL https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/main/install-mac-gnome-ultimate-wip.sh | bash -
```

Run from your desktop account; the bootstrap asks for sudo. Root can add
`--user ACCOUNT`. Reboot when ready and sign into **Omarchy (GNOME)** using your
normal password. `--activate` switches to GDM after installation and closes the
current graphical session. `--check` checks the package platform and desktop
account without installing anything.

## Desktop integration

The installer selects the GNOME session through AccountsService, disables GDM
automatic/timed login, and makes GDM the default display manager. KDE, SDDM and
Hyprland remain installed when already present. The KDE installer can select
Plasma Login Manager again.

The session runs stock GNOME Shell with its standard appearance and GNOME's
scaling, settings and portals. It removes stale Hyprland/Plasma environment
settings and adds GNOME-aware launch, lock and logout wrappers for existing
Omarchy helpers. Omarchy services that depend on Hyprland are skipped inside
GNOME using per-user systemd conditions; they remain available in other desktops.
Omarchy's Mac display-readiness and first-boot conditions are carried into GDM.
Personal power, locking and theme preferences are not overwritten by installation.

An explicit current app set is installed instead of the whole `gnome` package
group: the tested repositories contained obsolete GNOME Books/Boxes builds whose
removed libraries prevented the group transaction. Included apps cover Files,
Console, Text Editor, Settings, Software, Calendar, Contacts, Clocks, Calculator,
Disks, Logs, System Monitor, Fonts, Image Viewer, Document Viewer, Video Player,
Camera, Document Scanner, Tweaks and Help. Packages use the shared official Arch
Linux ARM cache fallback with repository hashes/signatures retained.

## Files and recovery

Runtime helpers live in `/usr/local/lib/omarchy-gnome`. The session entry is
`/usr/share/wayland-sessions/omarchy-gnome.desktop`; GDM uses `/etc/gdm/custom.conf`.
Backups of the previous login-manager selection, GDM configuration and account
session settings are saved in `/var/lib/omarchy-gnome/backups/TIMESTAMP-PID/`.
User integration files are under `~/.config/systemd/` with a state marker in
`~/.local/state/omarchy-gnome/`.

To restore SDDM, save open work and run:

```bash
sudo systemctl disable gdm.service
sudo systemctl enable --force sddm.service
```

Then reboot and select your previous session. If Plasma Login Manager was used,
substitute `plasmalogin.service` for `sddm.service`. The immediate switch helper
attempts to restart the previous manager if starting GDM returns an error; this
does not detect every possible later greeter failure.

## Validation

On 2026-11-04 the installer completed on the owner's M3 Pro running Omarchy,
kernel `7.2.11-14-1-ARCH`, and GNOME 51. The owner signed in through GDM's normal
password prompt; the selected session started GNOME Wayland. GNOME Settings and
Console were launched and inspected on the real display. No kernel or Steam
changes were needed for this desktop installation.

The initial global-shortcut permission dialog showed missing individual glyphs.
The same process rendered the full text correctly after a redraw. Both a default
GTK Vulkan text probe and an OpenGL probe rendered correctly, as did a fresh
Settings window. Installed Adwaita fonts resolve correctly. This is evidence of
a transient rendering problem, not a missing-font package; its underlying cause
has not been isolated. No unverified global GTK renderer override is installed.

Portable checks cover password/session configuration, preservation of other
desktops, environment cleanup, and literal launcher arguments:

```bash
python3 -m unittest discover -s gnome/tests -v
```
