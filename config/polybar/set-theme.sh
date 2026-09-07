#!/usr/bin/env bash
# ==========================================================
# set-theme.sh - Switch Polybar color themes seamlessly
# ==========================================================
set -euo pipefail

THEMES_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/polybar/themes"
CURRENT_LINK="${XDG_CONFIG_HOME:-$HOME/.config}/polybar/current_theme.ini"

usage() {
    echo "Usage: $0 [THEME_NAME | --list]"
    echo ""
    echo "Available themes in $THEMES_DIR:"
    for t in "$THEMES_DIR"/*.ini; do
        if [ -f "$t" ]; then
            name=$(basename "$t" .ini)
            if [ -L "$CURRENT_LINK" ] && [ "$(readlink -f "$CURRENT_LINK")" = "$(readlink -f "$t")" ]; then
                echo "  * $name (active)"
            else
                echo "    $name"
            fi
        fi
    done
}

if [ $# -eq 0 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    usage
    exit 0
fi

if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
    for t in "$THEMES_DIR"/*.ini; do
        [ -f "$t" ] && basename "$t" .ini
    done
    exit 0
fi

THEME_NAME="$1"
TARGET_FILE="$THEMES_DIR/${THEME_NAME}.ini"

if [ ! -f "$TARGET_FILE" ]; then
    echo "Error: Theme '$THEME_NAME' not found in $THEMES_DIR" >&2
    echo "Run '$0 --list' to view available themes." >&2
    exit 1
fi

ln -sf "themes/${THEME_NAME}.ini" "$CURRENT_LINK"
echo "Switched Polybar theme to '$THEME_NAME'."

# Reload polybar if running
if pgrep -u "$UID" -x polybar >/dev/null 2>&1; then
    "${XDG_CONFIG_HOME:-$HOME/.config}/polybar/launch.sh"
    echo "Polybar reloaded."
fi
