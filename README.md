# i3wm Desktop Environment Dotfiles

A consolidated, reproducible, and version-controlled configuration for the i3wm desktop environment on this workstation.

---

## 🧭 Overview

This repository centralizes all configurations, daemons, and helper scripts that define the look, feel, and workflow behavior of the desktop environment.

Key components:
- **Window Manager**: [i3wm](https://i3wm.org/) with gaps, custom layouts, and keybindings.
- **Status Bar & Floating Docks**: Tri-[Polybar](https://polybar.github.io/) pill architecture with picom dual-kawase blur:
  - **Apps Dock (Left Flank)**: 20% width floating pill ($x = 86..774$, 2.5% buffer) displaying dynamic clickable app icons.
  - **Main Bar (Center Master)**: 50% width centered pill ($x = 860..2580$) with workspaces, active window title, MPRIS media control, wallpaper switcher, Antigravity quota meter, volume, and clock.
  - **System HUD (Right Flank)**: 20% width floating pill ($x = 2666..3354$, 77.5% offset) hosting Bluetooth, WiFi, Disk space, RAM, and CPU telemetry with Nerd Font iconography.
  - **Dock Manager GUI**: GTK3 Nord-themed manager (`apps_settings.py` / `$mod+Shift+d`) to add, edit, remove, and reorder dock apps with live reload.
  - **Theme System**: Modular themes in `config/polybar/themes/` switchable via `~/.config/polybar/set-theme.sh` with live hot-reloading.
- **Compositor**: [Picom](https://github.com/yshui/picom) with GLX backend, dual-kawase background blur (enabled on semi-transparent dock pills), soft drop shadows, and rounded corners (8px).
- **Ultrawide Centered Master Layout**: Custom daemon (`i3-single-center.py`) using i3 IPC sockets to maintain a fixed 50% width centered pane under Polybar, dynamically growing and stacking side tiles around it (Left 25% first, Right 25% second, then vertical stacking). Also provides `$mod+m` to promote any tile to Center Master.
- **Multiplexer**: `tmux` configured with the matching Nord color scheme and Powerline status line.

---

## 📁 Repository Structure

```
dotfiles/
├── bin/                                # Custom user binaries (symlinked to ~/.local/bin/)
│   ├── i3-single-center.py            # Ultrawide auto-centering daemon via i3 IPC
│   └── wallpaper_rotator.py           # Random wallpaper switcher (feh backend)
├── config/                             # XDG config directories (symlinked to ~/.config/)
│   ├── dunst/
│   │   └── dunstrc.d/
│   │       └── 10-mouse-actions.conf  # Notification mouse click overrides
│   ├── i3/
│   │   └── config                     # Main i3wm configuration (Nord theme, gaps, keybindings)
│   ├── picom/
│   │   └── picom.conf                 # GLX compositor, dual-kawase blur, shadows, rounded corners
│   └── polybar/
│       ├── config.ini                 # Tri-bar Polybar configuration (apps, main, right)
│       ├── current_theme.ini          # Active theme symlink (default: themes/default.ini)
│       ├── themes/                    # Modular color palettes
│       │   ├── default.ini            # Semi-transparent Nord theme
│       │   ├── dracula.ini            # Dracula palette
│       │   └── catppuccin-mocha.ini   # Catppuccin Mocha palette
│       ├── set-theme.sh               # CLI theme switcher tool with live reload
│       ├── launch.sh                  # Multi-instance daemon launcher (apps + main + right)
│       ├── apps.json                  # Pinned apps configuration
│       ├── apps_dock.py               # Clickable Nerd Font app launcher module
│       ├── apps_settings.py           # GTK3 Nord-themed Apps Dock GUI manager
│       ├── player.sh                  # MPRIS media player controller (playerctl)
│       ├── bluetooth.sh               # Bluetooth status & quick control with Nerd Font icons
│       ├── torrent.sh                 # Transmission daemon status & transfer speeds
│       └── antivirus.py               # Google Antigravity quota visual meter & notifications
├── home/                               # Dotfiles placed directly in $HOME
│   ├── .fehbg                         # Active wallpaper restore script
│   ├── .tmux.conf                     # Nord-themed tmux configuration
│   └── .xinitrc                       # X session startup (exec i3)
├── install.sh                          # Idempotent installer & symlink manager
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### Installation & Symlink Creation
```bash
./install.sh
```

### Checking Symlink Status
```bash
./install.sh --status
```

### In-Place Hot Reloading
```bash
./install.sh --reload
```

### Switching Polybar Color Themes
```bash
# List available themes
~/.config/polybar/set-theme.sh --list

# Switch to Dracula or Catppuccin Mocha with live reload
~/.config/polybar/set-theme.sh dracula
~/.config/polybar/set-theme.sh catppuccin-mocha

# Return to default
~/.config/polybar/set-theme.sh default
```

---

## 💡 Key Features & Custom Modules

### Apps Dock (`bar/apps`)
- Located on the left flank at $x = 86\text{px}$ ($2.5\%$ screen offset).
- Renders clickable application icons defined in `config/polybar/apps.json`.
- Right-click anywhere on the dock or click the settings gear (󰒓) to launch the GTK3 Apps Manager.

### Main Bar (`bar/main`)
- Centered directly over the Center Master window ($50\%$ screen width).
- Workspaces, active window title, MPRIS controls, wallpaper rotator, Antigravity quota meter, volume, and clock.

### System HUD (`bar/right`)
- Symmetrically balances the left apps dock on the right flank at $x = 2666\text{px}$ ($77.5\%$ screen offset, $20\%$ width).
- Monitors hardware and connectivity with clean Nerd Font icons:
  - 󰂱 / 󰂯 Bluetooth status (click opens Blueman, right-click toggles power)
  - 󰖩 WiFi network SSID
  - 󰋊 Root filesystem usage percentage
  - 󰍛 Memory / RAM usage percentage
  - 󰻠 CPU load percentage

### Ultrawide Centered Master Layout (`bin/i3-single-center.py`)
- Continuously listens on the i3 IPC UNIX socket for `workspace` and `window` events.
- **1 Tiled Window**: Centered under Polybar at 50% screen width ($x = 860$, width = $1720\text{px}$).
- **2 Tiled Windows**: The Center Master remains 100% untouched; the second window opens on the **Left** at 25% width ($860\text{px}$), with asymmetric gaps keeping the right margin empty.
- **3 Tiled Windows**: Center Master remains untouched; the third window opens on the **Right** at 25% width ($860\text{px}$).
- **4+ Tiled Windows**: Additional windows stack vertically in the Left and Right columns alternating around the fixed 50% Center Master.
- **Closing Windows**: Columns smoothly step backward down the progression as windows close. If the Master window closes, the active side tile promotes to Master.
- **Promote Shortcut**: Press `Mod4 + m` to instantly swap the currently focused window into the Center Master position.

### Wallpaper Rotator (`bin/wallpaper_rotator.py`)
- Picks a random image from `~/wall/`.
- Sets wallpaper via `feh --bg-scale`.
- Bound to the wallpaper icon in Polybar and runs automatically on session startup.

---

## 🛠️ Iterating & Making UX Improvements

When starting a new UX improvement session:
1. All changes can be made directly in `~/proj/dotfiles/` (or via `~/dotfiles/`).
2. Changes are immediately reflected at runtime because the system paths are symlinked.
3. Test your changes in real-time:
   - i3 reload: `Mod4 + Shift + r` (inplace restart) or `Mod4 + Shift + c` (reload).
   - Polybar reload: Run `~/.config/polybar/launch.sh`.
   - Or run `./install.sh --reload` from this folder.
4. Add new configs:
   - Any new directory placed in `config/<name>` will be symlinked to `~/.config/<name>`.
   - Any new script placed in `bin/<script>` will be symlinked to `~/.local/bin/<script>`.
   - Any new dotfile placed in `home/<dotfile>` will be symlinked to `~/<dotfile>`.
5. Commit and track improvements with `git`:
   ```bash
   git add -A
   git commit -m "ux: tweak polybar spacing and picom shadow radius"
   ```

---

## 🔄 Unlinking / Restoring
To remove the managed symlinks:
```bash
./install.sh --unlink
```
To restore previously backed up files, copy them back from `~/.dotfiles_backup/`.
