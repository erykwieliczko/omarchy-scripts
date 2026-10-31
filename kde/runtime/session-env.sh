#!/bin/sh
# Sourced by Plasma; keep Omarchy applications usable in a native KDE session.
export OMARCHY_PATH=/usr/share/omarchy
case :$PATH: in
    *:/usr/local/lib/omarchy-kde/bin:*) ;;
    *) PATH="/usr/local/lib/omarchy-kde/bin:$PATH" ;;
esac
export PATH
export QT_QPA_PLATFORMTHEME=kde
export GTK_IM_MODULE=fcitx
unset QT_IM_MODULE
unset HYPRLAND_INSTANCE_SIGNATURE HYPRLAND_CMD HYPRCURSOR_THEME HYPRCURSOR_SIZE
unset GDK_SCALE GDK_DPI_SCALE QT_SCALE_FACTOR QT_SCREEN_SCALE_FACTORS
unset QT_QPA_PLATFORM QT_STYLE_OVERRIDE GTK_THEME
