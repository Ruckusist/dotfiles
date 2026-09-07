#!/usr/bin/env python3
"""
i3-single-center.py (Centered-Master Layout Manager)
Dynamically manages a Centered Master 3-column tiling layout on ultrawide displays in i3wm.

Layout Progression:
- 1 Window: Centered Master occupying 50% width directly under Polybar (left/right outer gaps = 848px).
- 2 Windows: Master remains fixed at 50% width centered; new window tiles on the Left (25% width).
  Asymmetric gaps: left = 2px, right = 848px.
- 3 Windows: Master remains fixed at 50% width centered; 3rd window tiles on the Right (25% width).
  Symmetric gaps: left = 2px, right = 2px.
- 4+ Windows: Windows stack vertically in the Left and Right columns alternating around the fixed
  50% Center Master.
- Window Closing: Layout seamlessly shrinks back down (5 -> 4 -> 3 -> 2 -> 1). If the Master window
  closes, the surviving active tile is promoted to Master.
- Keybinding: Supports '--promote' flag to swap the currently focused window into the Center Master.
"""

import os
import sys
import time
import socket
import struct
import json
import subprocess
import select
import signal
import fcntl

LOCK_FILE = "/tmp/i3-single-center.pid"
DEFAULT_OUTER_GAP = 2
INNER_GAP = 10
TOP_GAP = 46

def get_socket_path():
    sock = os.environ.get("I3SOCK")
    if sock and os.path.exists(sock):
        return sock
    return subprocess.check_output(["i3", "--get-socketpath"]).decode().strip()

class I3IPC:
    def __init__(self, sock_path):
        self.sock_path = sock_path
        self.cmd_sock = None
        self.ev_sock = None
        self.connect()

    def connect(self):
        if self.cmd_sock:
            try:
                self.cmd_sock.close()
            except Exception:
                pass
        if self.ev_sock:
            try:
                self.ev_sock.close()
            except Exception:
                pass

        self.cmd_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.cmd_sock.connect(self.sock_path)
        self.ev_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.ev_sock.connect(self.sock_path)

    def send_cmd(self, msg_type, payload=""):
        magic = b"i3-ipc"
        payload_bytes = payload.encode("utf-8")
        header = struct.pack("<6sII", magic, len(payload_bytes), msg_type)
        self.cmd_sock.sendall(header + payload_bytes)
        resp_header = self._recv_all(self.cmd_sock, 14)
        if not resp_header:
            return None
        r_magic, r_len, r_type = struct.unpack("<6sII", resp_header)
        data = self._recv_all(self.cmd_sock, r_len)
        if not data:
            return None
        return json.loads(data.decode("utf-8"))

    def subscribe(self, events):
        magic = b"i3-ipc"
        payload = json.dumps(events).encode("utf-8")
        header = struct.pack("<6sII", magic, len(payload), 2)
        self.ev_sock.sendall(header + payload)
        resp_header = self._recv_all(self.ev_sock, 14)
        if not resp_header:
            return False
        r_magic, r_len, r_type = struct.unpack("<6sII", resp_header)
        data = self._recv_all(self.ev_sock, r_len)
        if not data:
            return False
        return json.loads(data.decode("utf-8")).get("success", False)

    def recv_event(self):
        resp_header = self._recv_all(self.ev_sock, 14)
        if not resp_header:
            return None, None
        magic, length, ev_type = struct.unpack("<6sII", resp_header)
        data = self._recv_all(self.ev_sock, length)
        if not data:
            return None, None
        return ev_type, json.loads(data.decode("utf-8"))

    def _recv_all(self, sock, n):
        data = b""
        while len(data) < n:
            try:
                chunk = sock.recv(min(4096, n - len(data)))
                if not chunk:
                    return None
                data += chunk
            except Exception:
                return None
        return data

    def close(self):
        try:
            if self.cmd_sock:
                self.cmd_sock.close()
        except Exception:
            pass
        try:
            if self.ev_sock:
                self.ev_sock.close()
        except Exception:
            pass

def find_focused_workspace(tree):
    def search(node, current_ws=None):
        if node.get("type") == "workspace":
            current_ws = node
        if node.get("focused"):
            return current_ws
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            res = search(child, current_ws)
            if res:
                return res
        return None
    return search(tree)

def find_workspace_output(tree, ws_name):
    def search(node, current_output=None):
        if node.get("type") == "output":
            current_output = node
        if node.get("type") == "workspace" and node.get("name") == ws_name:
            return current_output
        for child in node.get("nodes", []):
            res = search(child, current_output)
            if res:
                return res
        return None
    return search(tree)

def get_tiled_windows(node):
    res = []
    if node.get("window"):
        res.append(node)
    for child in node.get("nodes", []):
        res.extend(get_tiled_windows(child))
    return res

class CenteredMasterManager:
    def __init__(self, ipc):
        self.ipc = ipc
        # ws_name -> {"master_id": int, "left_ids": [int], "right_ids": [int]}
        self.states = {}
        self.is_updating = False

    def update_workspace(self, ws, output_width=3440):
        if not ws or self.is_updating:
            return
        ws_name = ws.get("name")
        if ws_name == "__i3_scratch":
            return

        tiled_wins = get_tiled_windows(ws)
        total_wins = len(tiled_wins)
        tiled_win_ids = set(w["id"] for w in tiled_wins)

        # Single window gap (for 50% width centered)
        single_gap = int((output_width * 0.25) - INNER_GAP)

        if total_wins == 0:
            self.states.pop(ws_name, None)
            self._set_gaps(ws, single_gap, single_gap)
            return

        if total_wins == 1:
            win_id = tiled_wins[0]["id"]
            self.states[ws_name] = {
                "master_id": win_id,
                "left_ids": [],
                "right_ids": []
            }
            self._set_gaps(ws, single_gap, single_gap)
            return

        self.is_updating = True
        try:
            state = self.states.get(ws_name, {"master_id": None, "left_ids": [], "right_ids": []})
            master_id = state.get("master_id")

            # If master died or not set, pick the oldest or currently focused window
            if master_id not in tiled_win_ids:
                prior_candidates = state.get("left_ids", []) + state.get("right_ids", [])
                promoted = None
                for cid in prior_candidates:
                    if cid in tiled_win_ids:
                        promoted = cid
                        break
                if promoted:
                    master_id = promoted
                else:
                    master_id = tiled_wins[0]["id"]
                state["master_id"] = master_id
                state["left_ids"] = []
                state["right_ids"] = []

            # Filter out dead windows
            left_ids = [cid for cid in state.get("left_ids", []) if cid in tiled_win_ids and cid != master_id]
            right_ids = [cid for cid in state.get("right_ids", []) if cid in tiled_win_ids and cid != master_id]

            known_ids = set([master_id] + left_ids + right_ids)
            new_ids = [w["id"] for w in tiled_wins if w["id"] not in known_ids]

            # Allocate new windows:
            # First new window -> Left column
            # Second new window -> Right column
            # Third new window -> Left column stack
            # Fourth new window -> Right column stack
            for nid in new_ids:
                if len(left_ids) == 0:
                    left_ids.append(nid)
                elif len(right_ids) < len(left_ids):
                    right_ids.append(nid)
                else:
                    left_ids.append(nid)

            state["left_ids"] = left_ids
            state["right_ids"] = right_ids
            self.states[ws_name] = state

            # Apply layout & gaps
            if len(right_ids) == 0 and len(left_ids) == 1:
                # 2 Windows: Left (25%) + Center Master (50%) + Empty Right Margin (25%)
                self._set_gaps(ws, DEFAULT_OUTER_GAP, single_gap)
                self._arrange_two_windows(ws, left_ids[0], master_id)
            else:
                # 3+ Windows: Left (25%) + Center Master (50%) + Right (25%)
                self._set_gaps(ws, DEFAULT_OUTER_GAP, DEFAULT_OUTER_GAP)
                self._arrange_multi_windows(ws, left_ids, master_id, right_ids)
        finally:
            self.is_updating = False

    def promote_focused(self, ws):
        if not ws:
            return
        ws_name = ws.get("name")
        state = self.states.get(ws_name)
        if not state:
            return

        current_master = state.get("master_id")
        tiled_wins = get_tiled_windows(ws)
        focused_win = None
        for w in tiled_wins:
            if w.get("focused"):
                focused_win = w
                break

        if not focused_win or focused_win["id"] == current_master:
            return

        new_master_id = focused_win["id"]

        # Swap in i3 tree
        self.ipc.send_cmd(0, f"[con_id={new_master_id}] swap container with con_id {current_master}")

        # Swap in state
        left_ids = state.get("left_ids", [])
        right_ids = state.get("right_ids", [])

        if new_master_id in left_ids:
            idx = left_ids.index(new_master_id)
            left_ids[idx] = current_master
        elif new_master_id in right_ids:
            idx = right_ids.index(new_master_id)
            right_ids[idx] = current_master

        state["master_id"] = new_master_id
        state["left_ids"] = left_ids
        state["right_ids"] = right_ids
        self.states[ws_name] = state

        # Re-apply layout
        tree = self.ipc.send_cmd(4)
        updated_ws = find_focused_workspace(tree)
        if updated_ws:
            self.update_workspace(updated_ws)

    def _set_gaps(self, ws, left_gap, right_gap):
        current_gaps = ws.get("gaps", {})
        c_left = current_gaps.get("left", 0) + DEFAULT_OUTER_GAP
        c_right = current_gaps.get("right", 0) + DEFAULT_OUTER_GAP

        if abs(c_left - left_gap) > 5 or abs(c_right - right_gap) > 5:
            self.ipc.send_cmd(0, f"gaps left current set {left_gap}; gaps right current set {right_gap}; gaps top current set {TOP_GAP}; gaps bottom current set {DEFAULT_OUTER_GAP}")

    def _arrange_two_windows(self, ws, left_id, master_id):
        cmds = []
        cmds.append(f"[con_id={master_id}] layout splith")
        cmds.append(f"[con_id={left_id}] move left; [con_id={left_id}] move left")
        cmds.append(f"[con_id={master_id}] resize set width 67 ppt")
        cmds.append(f"[con_id={left_id}] resize set width 33 ppt")
        self.ipc.send_cmd(0, "; ".join(cmds))

    def _arrange_multi_windows(self, ws, left_ids, master_id, right_ids):
        cmds = []
        cmds.append(f"[con_id={master_id}] layout splith")

        # 1. Left column
        if left_ids:
            first_left = left_ids[0]
            cmds.append(f"[con_id={first_left}] move left; [con_id={first_left}] move left; [con_id={first_left}] move left")
            if len(left_ids) > 1:
                cmds.append(f"[con_id={first_left}] split vertical; [con_id={first_left}] mark --add _l_stack")
                for other_lid in left_ids[1:]:
                    cmds.append(f"[con_id={other_lid}] move container to mark _l_stack")

        # 2. Right column
        if right_ids:
            first_right = right_ids[0]
            cmds.append(f"[con_id={first_right}] move right; [con_id={first_right}] move right; [con_id={first_right}] move right")
            if len(right_ids) > 1:
                cmds.append(f"[con_id={first_right}] split vertical; [con_id={first_right}] mark --add _r_stack")
                for other_rid in right_ids[1:]:
                    cmds.append(f"[con_id={other_rid}] move container to mark _r_stack")

        # Set widths: master 50 ppt, left 25 ppt, right 25 ppt
        cmds.append(f"[con_id={master_id}] resize set width 50 ppt")
        if left_ids:
            cmds.append(f"[con_id={left_ids[0]}] resize set width 25 ppt")
        if right_ids:
            cmds.append(f"[con_id={right_ids[0]}] resize set width 25 ppt")

        self.ipc.send_cmd(0, "; ".join(cmds))

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                try:
                    os.kill(old_pid, signal.SIGTERM)
                    time.sleep(0.15)
                except ProcessLookupError:
                    pass
        except Exception:
            pass

    lock_file = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file
    except BlockingIOError:
        print("Another instance of i3-single-center is already running.")
        sys.exit(0)

def main():
    sock_path = get_socket_path()

    # If invoked with --promote, perform quick swap and exit
    if len(sys.argv) > 1 and sys.argv[1] == "--promote":
        ipc = I3IPC(sock_path)
        tree = ipc.send_cmd(4)
        ws = find_focused_workspace(tree)
        if ws:
            mgr = CenteredMasterManager(ipc)
            mgr.update_workspace(ws)
            mgr.promote_focused(ws)
        ipc.close()
        sys.exit(0)

    lock_file = acquire_lock()

    running = True
    def sig_handler(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    while running:
        try:
            ipc = I3IPC(sock_path)
            if not ipc.subscribe(["workspace", "window"]):
                time.sleep(1)
                continue

            mgr = CenteredMasterManager(ipc)
            tree = ipc.send_cmd(4)
            ws = find_focused_workspace(tree)
            if ws:
                output_node = find_workspace_output(tree, ws.get("name"))
                width = output_node["rect"]["width"] if output_node and "rect" in output_node else 3440
                mgr.update_workspace(ws, output_width=width)

            while running:
                r, _, _ = select.select([ipc.ev_sock], [], [], 0.5)
                if not r:
                    continue

                ev_type, ev_data = ipc.recv_event()
                if ev_data is None:
                    break

                # Drain burst events within 30ms
                while True:
                    r_drain, _, _ = select.select([ipc.ev_sock], [], [], 0.03)
                    if not r_drain:
                        break
                    _, extra = ipc.recv_event()
                    if extra is None:
                        break

                tree = ipc.send_cmd(4)
                ws = find_focused_workspace(tree)
                if ws:
                    output_node = find_workspace_output(tree, ws.get("name"))
                    width = output_node["rect"]["width"] if output_node and "rect" in output_node else 3440
                    mgr.update_workspace(ws, output_width=width)

            ipc.close()
        except (ConnectionResetError, BrokenPipeError, FileNotFoundError):
            time.sleep(0.5)
        except Exception:
            time.sleep(1)

    try:
        lock_file.close()
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

if __name__ == "__main__":
    main()
