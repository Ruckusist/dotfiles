# i3wm Desktop Environment Dotfiles

A consolidated, reproducible, and version-controlled configuration for the i3wm desktop environment on this workstation.

---

## 🧭 Overview

This repository centralizes all configurations, daemons, and helper scripts that define the look, feel, and workflow behavior of the desktop environment.

Key components:
- **Window Manager**: [i3wm](https://i3wm.org/) with gaps, custom layouts, and keybindings.
- **Status Bar**: [Polybar](https://polybar.github.io/) styled with rounded corners, custom modules (Antigravity quota, MPRIS media control, Bluetooth, Torrents, WiFi, hardware monitors).
- **Compositor**: [Picom](https://github.com/yshui/picom) with GLX backend, dual-kawase background blur, soft drop shadows, and rounded corners (8px).
- **Notifications**: [Dunst](https://dunst-project.org/) with left-click default action activation.
- **Ultrawide Window Centering**: Custom daemon (`i3-single-center.py`) using i3 IPC sockets to automatically center single windows at 50% screen width directly under Polybar on ultrawide monitors.
- **Wallpaper Rotator**: `wallpaper_rotator.py` + `feh` for random wallpaper cycling from `~/wall`.
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
│   │   └── picom.conf                 # GLX compositor, blur, shadows, rounded corners
│   └── polybar/
│       ├── config.ini                 # Main Polybar configuration and module layout
│       ├── launch.sh                  # Process supervisor & multi-monitor launcher
│       ├── player.sh                  # MPRIS media player controller (playerctl)
│       ├── bluetooth.sh               # Bluetooth status & quick control
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

### 1. Check Symlink Status
Inspect which configurations are currently linked or unmanaged:
```bash
./install.sh --status
```

### 2. Verify Dependencies
Check what core and optional packages are installed on your system:
```bash
./install.sh --check-deps
```

### 3. Dry Run
Preview all backup and symlinking operations before making any changes:
```bash
./install.sh --dry-run
```

### 4. Install & Link
Consolidate and softlink all configurations into `~/.config`, `~/.local/bin`, and `~`:
```bash
./install.sh
```
> **Note**: Any existing non-symlink configuration files are automatically backed up to `~/.dotfiles_backup/<timestamp>/` before creating the symlinks.

### 5. Reload Running Environment
Reload i3wm, Polybar, Picom, and Dunst in-place:
```bash
./install.sh --reload
```

---

## ⚙️ Component Details

### i3 Window Manager (`config/i3/config`)
- **Modifier Key**: `Mod4` (Super / Windows key).
- **Font**: JetBrains Mono 9.
- **Gaps**: Inner 10px, Outer 2px, Top 46px (leaves space for Polybar).
- **Palette**: Nord Dark (`#2e3440`, `#3b4252`, `#4c566a`, `#88c0d0`, `#bf616a`).
- **Autostart Daemons**:
  - `picom --config ~/.config/picom/picom.conf -b`
  - `dunst`
  - `~/.config/polybar/launch.sh`
  - `~/.local/bin/i3-single-center.py`
  - `~/.local/bin/wallpaper_rotator.py`

### Polybar (`config/polybar/`)
- **Width**: 50% centered (`offset-x = 25%`) with 12px pill radius.
- **Modules**:
  - **Left**: `xworkspaces`, `xwindow`.
  - **Right**: `mpris`, `wallpaper`, `antivirus` (Antigravity quota), `filesystem`, `pulseaudio`, `bluetooth`, `wifi`, `memory`, `cpu`, `date`.
- **Antivirus (Antigravity Quota)**:
  - Left-click: Pops up a desktop notification with remaining 5h and weekly quota.
  - Right-click: Forces quota cache refresh.

### Ultrawide Auto-Centering (`bin/i3-single-center.py`)
- Continuously listens on the i3 IPC UNIX socket for `workspace` and `window` events.
- If a workspace contains **1 tiled window**, it calculates dynamic horizontal outer gaps such that the window occupies exactly 50% width directly centered under Polybar.
- If **2 or more windows** are opened, outer gaps revert to default (2px) for normal side-by-side tiling.

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
