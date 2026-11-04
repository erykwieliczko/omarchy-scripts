#!/bin/sh
# GNOME supplies its own scaling, input method, theme and desktop services.
export OMARCHY_PATH=/usr/share/omarchy
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | sed '\|^/usr/local/lib/omarchy-kde/bin$|d;\|^/usr/local/lib/omarchy-gnome/bin$|d' | paste -sd:)
export PATH="/usr/local/lib/omarchy-gnome/bin:$PATH"
export XDG_CURRENT_DESKTOP=GNOME XDG_SESSION_DESKTOP=gnome XDG_SESSION_TYPE=wayland
unset HYPRLAND_INSTANCE_SIGNATURE HYPRLAND_CMD HYPRCURSOR_THEME HYPRCURSOR_SIZE
unset GDK_SCALE GDK_DPI_SCALE GDK_BACKEND QT_SCALE_FACTOR QT_SCREEN_SCALE_FACTORS
unset QT_QPA_PLATFORM QT_STYLE_OVERRIDE QT_QPA_PLATFORMTHEME GTK_THEME
unset GTK_IM_MODULE QT_IM_MODULE SDL_IM_MODULE XMODIFIERS INPUT_METHOD
unset KDE_FULL_SESSION KDE_SESSION_VERSION KDE_SESSION_UID
