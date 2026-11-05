# Install Mac GNOME Ultimate WIP

Install a complete, Fedora-inspired GNOME desktop with GDM password login on an existing
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
Plasma Login Manager again. Immediate switches stop other managers individually;
an uninstalled manager cannot prevent the active one from being stopped.

The session runs stock GNOME Shell with its standard appearance and GNOME's
scaling, settings and portals. It removes stale Hyprland/Plasma environment
settings and adds GNOME-aware launch, lock and logout wrappers for existing
Omarchy helpers. Omarchy services that depend on Hyprland are skipped inside
GNOME using per-user systemd conditions; they remain available in other desktops.
Omarchy's Mac display-readiness and first-boot conditions are carried into GDM.
Personal power, locking and display preferences are not overwritten by installation.

The first run seeds a dark Adwaita desktop, dynamic workspaces, edge tiling,
minimize/maximize buttons, battery percentage and the weekday in the clock.
The MacBook touchpad gets tap-to-click, two-finger right-click and scrolling,
natural scrolling and typing protection. Native GNOME workspace/overview gestures
remain available. The favorites bar uses the existing default browser, Files,
Console, Text Editor, Software and Settings; an explicitly customized favorites
bar is preserved. The sole enabled extra Shell extension is Ubuntu's
AppIndicator support, for Steam and other background app tray icons. Official
GNOME extensions and their management app are installed for optional customization.
Newly installed extensions become available in an existing session after signing
out and back in.

Useful shortcuts include:

| Shortcut | Action |
| --- | --- |
| Super+Enter or Ctrl+Alt+T | Console |
| Super+E | Files |
| Alt+Tab | Individual windows |
| Super+Tab | Applications |
| Super+Left / Right | Tile a window |

These preferences are applied once. Later changes survive installer reruns.
GNOME also starts with the currently selected Omarchy wallpaper, or a bundled
Tokyo Night still image if none is selected. Both light and dark modes use it.
The installer keeps a stable copy in `~/.local/share/backgrounds/omarchy-gnome/`
so switching Omarchy themes does not remove GNOME's background. This also upgrades
earlier installations still using GNOME's default; an explicit wallpaper choice
in GNOME Settings is preserved. It applies once, with a separate
`wallpaper-default-v1` marker and `wallpaper-before-*.json` backup under the same
state directory. Animated Omarchy backgrounds are skipped in favor of a still image.
Prior values are backed up in `~/.local/state/omarchy-gnome/desktop-before-*.json`;
restore one as your desktop user with
`python3 /usr/local/lib/omarchy-gnome/desktop-defaults.py --restore BACKUP.json`.
Your existing custom shortcuts are retained. The profile does not change monitor
resolution, scaling, refresh rate, keyboard layout, browser choice or idle policy.

GNOME uses its own IBus input service. Fcitx's XDG autostart is excluded only from
GNOME, and inherited Fcitx module variables are cleared from session and D-Bus
activation environments. This prevents Fcitx's IBus compatibility endpoint from
blocking GNOME's native input service; Fcitx remains usable in other desktops.
Partial legacy autostart masks are completed from the system desktop entry:
without the required fields, GNOME can ignore the mask and start Fcitx anyway.

An explicit current app set is installed instead of the whole `gnome` package
group: the tested repositories contained obsolete GNOME Books/Boxes builds whose
removed libraries prevented the group transaction. Included apps cover Files,
Console, Text Editor, Settings, Software, Calendar, Contacts, Clocks, Calculator,
Disks, Logs, System Monitor, Fonts, Image Viewer, Document Viewer, Video Player,
Camera, Document Scanner, Tweaks and Help. The full set also includes Weather,
Maps, Characters, Connections, Passwords and Keys, Disk Usage Analyzer, Archive
Manager, Audio Player, Geary mail, LibreOffice, the GNOME Tour, media codecs,
network file backends and Files' Space-key preview. Remote Desktop settings are
available without enabling unattended remote access.

Flatpak and a per-user Flathub remote make GNOME Software useful for graphical
app installation. Software manages Flatpak apps; keep using Omarchy's updater
for the base system. Existing Flathub configuration is preserved. No extra
Flatpak apps or shared runtimes are downloaded automatically.

When the host uses `mesa-aurora`, the installer also downloads the published
[Aurora Flatpak graphics package](https://github.com/aurora-silicon/alarm-aurora/tree/main/packages/aurora-flatpak-gl).
The archive is pinned by SHA-256. Only its GL extension repository and license
are extracted into `/usr/local/share/omarchy-gnome/flatpak-gl`; host Mesa, Vulkan
and kernel packages are retained. `org.freedesktop.Platform.GL.aurora` is installed
for Freedesktop 25.08 and 26.08 through a dedicated local per-user remote. Driver
selection follows Aurora's published GL extension layout; existing explicit
loader overrides are preserved, and prior overrides are backed up under
`~/.local/state/omarchy-gnome/`. The source URL, hash and upstream attribution are
recorded in `flatpak-gl/source.json`, and upstream licensing stays with the payload.
Other graphics stacks use their distribution's Flatpak drivers.

This is required on the tested M3: Flathub's default Mesa produced pink/blank
windows and `DRM_IOCTL_ASAHI_SUBMIT` errors against Aurora's kernel, in both GTK's
Vulkan and OpenGL renderers. Installing a compatible graphics extension fixes
the driver mismatch without a software-rendering override or sandbox filesystem
exceptions. Sign out and back in after an existing GNOME session is upgraded so
app launches inherit the new Flatpak driver selection.

Packages use the shared official Arch
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

The expanded profile was applied and the public installer rerun without resetting
later preferences. The panel retains 3024×1964 at 120 Hz with 200% scaling, and
the owner's no-idle/no-lock choices remain saved. Console opened with Ctrl+Alt+T;
a real GTK input test accepted both ordinary text and an accented character
after restoring native IBus. The user manager has no failed units. A real Flathub
installation completed; Flatseal rendered correctly after the Aurora GL extension
repair. GTK's diagnostics report **Apple M3 Pro (G15S B1), Vulkan device 0** as
the selected GPU. Neither a global GTK renderer override nor software rendering
is used for that test.

The initial global-shortcut permission dialog showed missing individual glyphs.
The same process rendered the full text correctly after a redraw. Both a default
GTK Vulkan text probe and an OpenGL probe rendered correctly, as did a fresh
Settings window. Installed Adwaita fonts resolve correctly. This is evidence of
a transient rendering problem, not a missing-font package; its underlying cause
has not been isolated. No unverified global GTK renderer override is installed.

Portable checks cover password/session configuration, preservation of other
desktops, environment cleanup, literal launcher arguments, profile backups and
preservation of later preferences, favorites, power policy and existing shortcuts:

```bash
python3 -m unittest discover -s gnome/tests -v
```
