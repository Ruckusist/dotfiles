#!/usr/bin/env python3
"""
apps_dock.py
Dynamic Polybar module script that renders clickable application icons
and a settings launcher from apps.json.
"""

import os
import json
import sys

CONFIG_FILE = os.path.expanduser("~/.config/polybar/apps.json")
DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "apps.json")

def load_apps():
    path = CONFIG_FILE if os.path.exists(CONFIG_FILE) else DEFAULT_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def main():
    apps = load_apps()
    segments = []

    # Primary colors from Nord palette
    icon_colors = ["#88C0D0", "#81A1C1", "#B48EAD", "#A3BE8C", "#EBCB8B", "#D08770"]

    for idx, app in enumerate(apps):
        icon = app.get("icon", "")
        cmd = app.get("cmd", "")
        name = app.get("name", "")
        color = icon_colors[idx % len(icon_colors)]

        # Polybar action block for left-click
        # %{A1:cmd:} content %{A}
        # T2 selects font-1 (larger Nerd Font size)
        segment = f"%{{A1:{cmd}:}}%{{F{color}}}%{{T2}}{icon}%{{T-}}%{{F-}}%{{A}}"
        segments.append(segment)

    # Settings gear at the end
    settings_cmd = "python3 ~/.config/polybar/apps_settings.py &"
    gear_segment = f"%{{A1:{settings_cmd}:}}%{{F#4C566A}}│%{{F-}} %{{F#88C0D0}}%{{T2}}󰒓%{{T-}}%{{F-}}%{{A}}"
    
    # Join with spacing
    output = "   ".join(segments) + "  " + gear_segment
    print(output)

if __name__ == "__main__":
    main()
