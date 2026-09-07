#!/usr/bin/env bash
# Polybar bluetooth status: shows off/on/connected-device-name.

if ! command -v bluetoothctl >/dev/null 2>&1; then
    echo " n/a"
    exit 0
fi

powered=$(bluetoothctl show | awk '/Powered:/{print $2}')
if [ "$powered" != "yes" ]; then
    echo " off"
    exit 0
fi

connected=$(bluetoothctl devices Connected)
if [ -n "$connected" ]; then
    name=$(echo "$connected" | head -n1 | cut -d' ' -f3-)
    echo " $name"
else
    echo " on"
fi
