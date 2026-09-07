#!/usr/bin/env bash

# This script checks if 'playerctl' is installed and gets the current playing song.
# It supports Spotify, VLC, Firefox, Chrome, and most modern media players.

if command -v playerctl >/dev/null 2>&1; then
    status=$(playerctl status 2>/dev/null)
    if [ "$status" = "Playing" ]; then
        echo "$(playerctl metadata --format '{{ artist }} - {{ title }}' | cut -c 1-50)"
    elif [ "$status" = "Paused" ]; then
        echo " $(playerctl metadata --format '{{ title }}' | cut -c 1-25)"
    else
        echo ""
    fi
else
    echo "playerctl not installed"
fi
