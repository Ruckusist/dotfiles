#!/usr/bin/env python3
"""
apps_settings.py
Nord-themed GTK3 settings interface to add, edit, remove, and reorder apps
in the Polybar Apps Dock.
"""

import os
import sys
import glob
import json
import configparser
import subprocess

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Pango

CONFIG_FILE = os.path.expanduser("~/.config/polybar/apps.json")
DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "apps.json")

# Mapping of common app keywords to Nerd Font icons
ICON_SUGGESTIONS = {
    "terminal": "",
    "alacritty": "",
    "kitty": "",
    "bash": "",
    "browser": "󰈹",
    "firefox": "󰈹",
    "chrome": "",
    "chromium": "",
    "code": "󰨞",
    "vscode": "󰨞",
    "editor": "󰷈",
    "file": "󰉋",
    "files": "󰉋",
    "mc": "󰉋",
    "thunar": "󰉋",
    "nautilus": "󰉋",
    "audio": "󰓃",
    "volume": "󰓃",
    "pavucontrol": "󰓃",
    "music": "",
    "spotify": "",
    "video": "",
    "mpv": "",
    "vlc": "󰕼",
    "system": "󰍛",
    "monitor": "󰍛",
    "htop": "󰍛",
    "btop": "󰍛",
    "bluetooth": "󰂯",
    "settings": "󰒓",
    "image": "",
    "feh": "",
    "gimp": "",
    "chat": "󰭹",
    "discord": "󰙯",
    "slack": "󰒱",
    "mail": "󰇮"
}

NORD_CSS = """
window {
    background-color: #2e3440;
    color: #eceff4;
    font-family: 'JetBrains Mono', monospace;
}

headerbar, .titlebar {
    background-color: #2e3440;
    color: #eceff4;
    border-bottom: 1px solid #3b4252;
}

treeview {
    background-color: #3b4252;
    color: #eceff4;
    border-radius: 8px;
    border: 1px solid #434c5e;
    padding: 6px;
}

treeview:selected {
    background-color: #4c566a;
    color: #88c0d0;
}

button {
    background-color: #3b4252;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}

button:hover {
    background-color: #434c5e;
    border-color: #88c0d0;
    color: #88c0d0;
}

button.suggested-action {
    background-color: #88c0d0;
    color: #2e3440;
    border: 1px solid #81a1c1;
}

button.suggested-action:hover {
    background-color: #8fbcbb;
    color: #2e3440;
}

button.destructive-action {
    background-color: #bf616a;
    color: #eceff4;
    border: 1px solid #d08770;
}

button.destructive-action:hover {
    background-color: #d08770;
}

entry {
    background-color: #3b4252;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 6px;
    padding: 6px;
}

entry:focus {
    border-color: #88c0d0;
}

combobox button {
    background-color: #3b4252;
    color: #eceff4;
}
"""

def get_suggested_icon(name, cmd):
    text = (name + " " + cmd).lower()
    for kw, icon in ICON_SUGGESTIONS.items():
        if kw in text:
            return icon
    return ""

def scan_desktop_apps():
    search_dirs = [
        "/usr/share/applications",
        "/var/lib/snapd/desktop/applications",
        os.path.expanduser("~/.local/share/applications")
    ]
    apps = []
    seen = set()
    for sdir in search_dirs:
        for fpath in glob.glob(os.path.join(sdir, "*.desktop")):
            fname = os.path.basename(fpath)
            if fname in seen:
                continue
            seen.add(fname)
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(fpath, encoding="utf-8")
                if cp.has_section("Desktop Entry"):
                    sec = cp["Desktop Entry"]
                    if sec.get("NoDisplay", "false").lower() == "true":
                        continue
                    name = sec.get("Name")
                    exec_cmd = sec.get("Exec")
                    if name and exec_cmd:
                        clean_cmd = " ".join([part for part in exec_cmd.split() if not part.startswith("%")])
                        apps.append({
                            "name": name,
                            "cmd": clean_cmd + " &",
                            "icon": get_suggested_icon(name, clean_cmd)
                        })
            except Exception:
                pass
    apps.sort(key=lambda x: x["name"].lower())
    return apps

class AddEditDialog(Gtk.Dialog):
    def __init__(self, parent, title="Add Application", app_data=None):
        super().__init__(title=title, transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(420, 280)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(16)
        content.set_margin_bottom(16)

        # Quick picker dropdown for installed desktop apps
        self.installed_apps = scan_desktop_apps()
        picker_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        picker_label = Gtk.Label(label="Pick Installed App:")
        picker_label.set_xalign(0)
        
        self.combo = Gtk.ComboBoxText()
        self.combo.append_text("-- Choose from Installed Applications --")
        for a in self.installed_apps:
            self.combo.append_text(f"{a['icon']}  {a['name']}")
        self.combo.set_active(0)
        self.combo.connect("changed", self.on_picker_changed)

        picker_box.pack_start(picker_label, False, False, 0)
        picker_box.pack_start(self.combo, True, True, 0)
        content.pack_start(picker_box, False, False, 0)

        # Form fields
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(12)

        # App Name
        grid.attach(Gtk.Label(label="App Name:", xalign=0), 0, 0, 1, 1)
        self.entry_name = Gtk.Entry()
        grid.attach(self.entry_name, 1, 0, 1, 1)

        # Icon
        grid.attach(Gtk.Label(label="Nerd Font Icon:", xalign=0), 0, 1, 1, 1)
        self.entry_icon = Gtk.Entry()
        self.entry_icon.set_width_chars(6)
        grid.attach(self.entry_icon, 1, 1, 1, 1)

        # Launch Command
        grid.attach(Gtk.Label(label="Command:", xalign=0), 0, 2, 1, 1)
        self.entry_cmd = Gtk.Entry()
        grid.attach(self.entry_cmd, 1, 2, 1, 1)

        content.pack_start(grid, True, True, 0)

        if app_data:
            self.entry_name.set_text(app_data.get("name", ""))
            self.entry_icon.set_text(app_data.get("icon", ""))
            self.entry_cmd.set_text(app_data.get("cmd", ""))
        else:
            self.entry_icon.set_text("")

        self.show_all()

    def on_picker_changed(self, combo):
        idx = combo.get_active()
        if idx > 0:
            selected = self.installed_apps[idx - 1]
            self.entry_name.set_text(selected["name"])
            self.entry_cmd.set_text(selected["cmd"])
            self.entry_icon.set_text(selected["icon"])

    def get_data(self):
        return {
            "name": self.entry_name.get_text().strip(),
            "icon": self.entry_icon.get_text().strip() or "",
            "cmd": self.entry_cmd.get_text().strip()
        }

class AppsSettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Apps Dock Settings")
        self.set_default_size(560, 480)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Apply Nord CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(NORD_CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        self.add(main_box)

        # Header Title
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='large' weight='bold' foreground='#88C0D0'>󰒓 Polybar Apps Dock Manager</span>")
        title_lbl.set_xalign(0)
        subtitle_lbl = Gtk.Label(label="Add, reorder, or remove application shortcuts pinned to your dock.")
        subtitle_lbl.set_xalign(0)
        header_box.pack_start(title_lbl, False, False, 0)
        header_box.pack_start(subtitle_lbl, False, False, 0)
        main_box.pack_start(header_box, False, False, 0)

        # Body: TreeView + Side Action Buttons
        body_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.pack_start(body_box, True, True, 0)

        # ListStore: [Icon (str), Name (str), Command (str)]
        self.store = Gtk.ListStore(str, str, str)
        self.load_data()

        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_headers_visible(True)

        # Columns
        renderer_icon = Gtk.CellRendererText()
        renderer_icon.set_property("scale", 1.2)
        renderer_icon.set_property("foreground", "#88C0D0")
        col_icon = Gtk.TreeViewColumn("Icon", renderer_icon, text=0)
        col_icon.set_min_width(50)
        self.treeview.append_column(col_icon)

        renderer_name = Gtk.CellRendererText()
        renderer_name.set_property("weight", Pango.Weight.BOLD)
        col_name = Gtk.TreeViewColumn("Application", renderer_name, text=1)
        col_name.set_min_width(140)
        self.treeview.append_column(col_name)

        renderer_cmd = Gtk.CellRendererText()
        renderer_cmd.set_property("foreground", "#D8DEE9")
        col_cmd = Gtk.TreeViewColumn("Command", renderer_cmd, text=2)
        col_cmd.set_expand(True)
        self.treeview.append_column(col_cmd)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.treeview)
        body_box.pack_start(scroll, True, True, 0)

        # Side Buttons (Reorder & Edit)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body_box.pack_start(btn_box, False, False, 0)

        self.btn_up = Gtk.Button(label="▲ Move Up")
        self.btn_up.connect("clicked", self.on_move_up)
        btn_box.pack_start(self.btn_up, False, False, 0)

        self.btn_down = Gtk.Button(label="▼ Move Down")
        self.btn_down.connect("clicked", self.on_move_down)
        btn_box.pack_start(self.btn_down, False, False, 0)

        btn_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        self.btn_add = Gtk.Button(label="➕ Add App")
        self.btn_add.connect("clicked", self.on_add_app)
        btn_box.pack_start(self.btn_add, False, False, 0)

        self.btn_edit = Gtk.Button(label="✏️ Edit")
        self.btn_edit.connect("clicked", self.on_edit_app)
        btn_box.pack_start(self.btn_edit, False, False, 0)

        self.btn_remove = Gtk.Button(label="🗑️ Remove")
        self.btn_remove.get_style_context().add_class("destructive-action")
        self.btn_remove.connect("clicked", self.on_remove_app)
        btn_box.pack_start(self.btn_remove, False, False, 0)

        # Bottom Bar
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main_box.pack_start(bottom_box, False, False, 0)

        btn_defaults = Gtk.Button(label="Reset Defaults")
        btn_defaults.connect("clicked", self.on_reset_defaults)
        bottom_box.pack_start(btn_defaults, False, False, 0)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        bottom_box.pack_end(btn_close, False, False, 0)

        btn_save = Gtk.Button(label="💾 Save & Apply")
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self.on_save_and_apply)
        bottom_box.pack_end(btn_save, False, False, 0)

    def load_data(self):
        self.store.clear()
        path = CONFIG_FILE if os.path.exists(CONFIG_FILE) else DEFAULT_FILE
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    apps = json.load(f)
                for a in apps:
                    self.store.append([a.get("icon", ""), a.get("name", ""), a.get("cmd", "")])
            except Exception:
                pass

    def on_move_up(self, btn):
        model, tree_iter = self.treeview.get_selection().get_selected()
        if not tree_iter:
            return
        idx = model.get_path(tree_iter).get_indices()[0]
        if idx > 0:
            prev_iter = model.get_iter(Gtk.TreePath.new_from_indices([idx - 1]))
            model.swap(tree_iter, prev_iter)

    def on_move_down(self, btn):
        model, tree_iter = self.treeview.get_selection().get_selected()
        if not tree_iter:
            return
        idx = model.get_path(tree_iter).get_indices()[0]
        if idx < len(model) - 1:
            next_iter = model.get_iter(Gtk.TreePath.new_from_indices([idx + 1]))
            model.swap(tree_iter, next_iter)

    def on_add_app(self, btn):
        dlg = AddEditDialog(self, title="Add Application to Dock")
        res = dlg.run()
        if res == Gtk.ResponseType.OK:
            data = dlg.get_data()
            if data["name"] and data["cmd"]:
                self.store.append([data["icon"], data["name"], data["cmd"]])
        dlg.destroy()

    def on_edit_app(self, btn):
        model, tree_iter = self.treeview.get_selection().get_selected()
        if not tree_iter:
            return
        app_data = {
            "icon": model.get_value(tree_iter, 0),
            "name": model.get_value(tree_iter, 1),
            "cmd": model.get_value(tree_iter, 2),
        }
        dlg = AddEditDialog(self, title="Edit Application", app_data=app_data)
        res = dlg.run()
        if res == Gtk.ResponseType.OK:
            data = dlg.get_data()
            model.set_value(tree_iter, 0, data["icon"])
            model.set_value(tree_iter, 1, data["name"])
            model.set_value(tree_iter, 2, data["cmd"])
        dlg.destroy()

    def on_remove_app(self, btn):
        model, tree_iter = self.treeview.get_selection().get_selected()
        if tree_iter:
            model.remove(tree_iter)

    def on_reset_defaults(self, btn):
        if os.path.exists(DEFAULT_FILE):
            try:
                with open(DEFAULT_FILE, "r", encoding="utf-8") as f:
                    apps = json.load(f)
                self.store.clear()
                for a in apps:
                    self.store.append([a.get("icon", ""), a.get("name", ""), a.get("cmd", "")])
            except Exception:
                pass

    def on_save_and_apply(self, btn):
        apps = []
        for row in self.store:
            apps.append({
                "icon": row[0],
                "name": row[1],
                "cmd": row[2]
            })

        target_file = CONFIG_FILE
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)

        # Notify desktop
        try:
            subprocess.run(["notify-send", "-a", "Polybar", "Apps Dock", "Application shortcuts updated successfully!"], check=False)
        except Exception:
            pass

def main():
    win = AppsSettingsWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
