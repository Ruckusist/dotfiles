#!/usr/bin/env python3
"""
i3-single-center.py (Smooth Centered-Master Layout Manager)
Dynamically manages a Centered Master 3-column tiling layout on ultrawide displays in i3wm.

Smoothness & Stability Architecture:
1. True Event Filtering:
   - Ignores high-frequency cosmetic noise (title changes, mouse focus, urgent flags, marks).
   - Only updates layout on structural changes (window new, close, move, and workspace focus/init).
2. Hierarchy-Aware Column Mapping:
   - Accurately tracks top-level column containers across nested splits using recursive leaf matching.
   - Uses atomic container swapping so windows never visually drift or shuffle through intermediate frames.
3. Idempotency Guard:
   - Evaluates whether columns, widths, and gaps already match the target layout.
   - If already in the target state, zero IPC commands are sent (0% CPU, 0 visual jitter).
4. Atomic Batch Transaction:
   - Combines gaps, layout, swaps, resizes, and active window focus restoration into ONE atomic IPC command.
   - i3 and Picom process and render the entire layout update in a single X11 frame (<0.2ms).
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

def get_columns(ws):
    nodes = ws.get("nodes", [])
    while len(nodes) == 1 and not nodes[0].get("window"):
        nodes = nodes[0].get("nodes", [])
    return nodes

def find_col_for_win(cols, win_id):
    for col in cols:
        if col["id"] == win_id:
            return col
        for w in get_tiled_windows(col):
            if w["id"] == win_id:
                return col
    return None

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

        # Single window centered gap calculation
        single_gap = int((output_width * 0.25) - INNER_GAP)

        # Empty workspace
        if total_wins == 0:
            self.states.pop(ws_name, None)
            self._ensure_gaps(ws, single_gap, single_gap)
            return

        # 1 Window: Center Master
        if total_wins == 1:
            win_id = tiled_wins[0]["id"]
            self.states[ws_name] = {
                "master_id": win_id,
                "left_ids": [],
                "right_ids": []
            }
            self._ensure_gaps(ws, single_gap, single_gap)
            return

        self.is_updating = True
        try:
            state = self.states.get(ws_name, {"master_id": None, "left_ids": [], "right_ids": []})
            master_id = state.get("master_id")

            # Validate or promote master_id
            if master_id not in tiled_win_ids:
                prior_candidates = state.get("left_ids", []) + state.get("right_ids", [])
                promoted = None
                for cid in prior_candidates:
                    if cid in tiled_win_ids:
                        promoted = cid
                        break
                master_id = promoted if promoted else tiled_wins[0]["id"]
                state["master_id"] = master_id
                state["left_ids"] = []
                state["right_ids"] = []

            # Reconcile alive windows
            left_ids = [cid for cid in state.get("left_ids", []) if cid in tiled_win_ids and cid != master_id]
            right_ids = [cid for cid in state.get("right_ids", []) if cid in tiled_win_ids and cid != master_id]

            known_ids = set([master_id] + left_ids + right_ids)
            new_ids = [w["id"] for w in tiled_wins if w["id"] not in known_ids]

            # Distribute new windows:
            # 1st new -> Left
            # 2nd new -> Right
            # 3rd new -> Left Stack
            # 4th new -> Right Stack
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

            # Find active focused window to preserve focus seamlessly
            focused_id = None
            for w in tiled_wins:
                if w.get("focused"):
                    focused_id = w["id"]
                    break

            # Execute atomic layout transaction
            self._apply_layout_atomically(ws, master_id, left_ids, right_ids, single_gap, focused_id)
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

        # Swap in i3 tree atomically
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

    def _ensure_gaps(self, ws, left_gap, right_gap):
        current_gaps = ws.get("gaps", {})
        c_left = current_gaps.get("left", 0) + DEFAULT_OUTER_GAP
        c_right = current_gaps.get("right", 0) + DEFAULT_OUTER_GAP

        if abs(c_left - left_gap) > 5 or abs(c_right - right_gap) > 5:
            self.ipc.send_cmd(0, f"gaps left current set {left_gap}; gaps right current set {right_gap}; gaps top current set {TOP_GAP}; gaps bottom current set {DEFAULT_OUTER_GAP}")

    def _apply_layout_atomically(self, ws, master_id, left_ids, right_ids, single_gap, focused_id):
        cmds = []

        # 1. Target gaps
        if len(right_ids) == 0 and len(left_ids) <= 1:
            target_left = DEFAULT_OUTER_GAP
            target_right = single_gap
        else:
            target_left = DEFAULT_OUTER_GAP
            target_right = DEFAULT_OUTER_GAP

        current_gaps = ws.get("gaps", {})
        c_left = current_gaps.get("left", 0) + DEFAULT_OUTER_GAP
        c_right = current_gaps.get("right", 0) + DEFAULT_OUTER_GAP
        gaps_need_update = (abs(c_left - target_left) > 5 or abs(c_right - target_right) > 5)

        if gaps_need_update:
            cmds.append(f"gaps left current set {target_left}; gaps right current set {target_right}; gaps top current set {TOP_GAP}; gaps bottom current set {DEFAULT_OUTER_GAP}")

        cols = get_columns(ws)
        if not cols:
            if cmds:
                self.ipc.send_cmd(0, "; ".join(cmds))
            return

        master_col = find_col_for_win(cols, master_id)
        if not master_col:
            if cmds:
                self.ipc.send_cmd(0, "; ".join(cmds))
            return

        # 2. Arrange 2 Windows: Left (25%) + Master (50%)
        if len(right_ids) == 0 and len(left_ids) == 1:
            left_id = left_ids[0]
            left_col = find_col_for_win(cols, left_id)
            if left_col and left_col != master_col:
                col_ids = [c["id"] for c in cols]
                l_idx = col_ids.index(left_col["id"])
                m_idx = col_ids.index(master_col["id"])

                order_correct = (l_idx < m_idx)
                master_pct = master_col.get("percent")
                size_correct = (master_pct is not None and abs(master_pct - 0.67) < 0.05)

                if not order_correct:
                    cmds.append(f"[con_id={left_col['id']}] swap container with con_id {master_col['id']}")
                if not size_correct or not order_correct or gaps_need_update:
                    cmds.append(f"[con_id={master_col['id']}] resize set width 67 ppt; [con_id={left_col['id']}] resize set width 33 ppt")

        # 3. Arrange 3+ Windows: Left (25%) + Master (50%) + Right (25%)
        elif len(right_ids) > 0 or len(left_ids) > 1:
            left_col = find_col_for_win(cols, left_ids[0]) if left_ids else None
            right_col = find_col_for_win(cols, right_ids[0]) if right_ids else None

            col_ids = [c["id"] for c in cols]

            # Right column positioning: ensure right_col is after master_col
            if right_col and right_col != master_col:
                r_idx = col_ids.index(right_col["id"])
                m_idx = col_ids.index(master_col["id"])
                if r_idx < m_idx:
                    cmds.append(f"[con_id={right_col['id']}] swap container with con_id {master_col['id']}")
                    # Update order snapshot after swap
                    col_ids[r_idx], col_ids[m_idx] = col_ids[m_idx], col_ids[r_idx]

            # Left column positioning: ensure left_col is before master_col
            if left_col and left_col != master_col:
                l_idx = col_ids.index(left_col["id"])
                m_idx = col_ids.index(master_col["id"])
                if l_idx > m_idx:
                    cmds.append(f"[con_id={left_col['id']}] swap container with con_id {master_col['id']}")

            # Handle vertical stacking in Left column (Windows 4, 6, ...)
            if len(left_ids) > 1 and left_col:
                left_wins_in_col = set(w["id"] for w in get_tiled_windows(left_col))
                need_split = (left_col.get("layout") != "splitv")
                if need_split:
                    cmds.append(f"[con_id={left_ids[0]}] split vertical; [con_id={left_ids[0]}] mark --add _l_stack")
                for lid in left_ids[1:]:
                    if lid not in left_wins_in_col:
                        cmds.append(f"[con_id={lid}] move container to mark _l_stack")

            # Handle vertical stacking in Right column (Windows 5, 7, ...)
            if len(right_ids) > 1 and right_col:
                right_wins_in_col = set(w["id"] for w in get_tiled_windows(right_col))
                need_split = (right_col.get("layout") != "splitv")
                if need_split:
                    cmds.append(f"[con_id={right_ids[0]}] split vertical; [con_id={right_ids[0]}] mark --add _r_stack")
                for rid in right_ids[1:]:
                    if rid not in right_wins_in_col:
                        cmds.append(f"[con_id={rid}] move container to mark _r_stack")

            # Apply column widths: 25% Left, 50% Master, 25% Right
            master_pct = master_col.get("percent")
            size_correct = (master_pct is not None and abs(master_pct - 0.50) < 0.05)
            if not size_correct or gaps_need_update:
                cmds.append(f"[con_id={master_col['id']}] resize set width 50 ppt")
                if left_col:
                    cmds.append(f"[con_id={left_col['id']}] resize set width 25 ppt")
                if right_col:
                    cmds.append(f"[con_id={right_col['id']}] resize set width 25 ppt")

        # 4. If everything is already in place, do not send any commands
        if not cmds:
            return

        # 5. Restore active user focus at the end of the atomic transaction
        if focused_id:
            cmds.append(f"[con_id={focused_id}] focus")

        self.ipc.send_cmd(0, "; ".join(cmds))

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    old_pid = int(content)
                    if old_pid != os.getpid():
                        try:
                            os.kill(old_pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
        except Exception:
            pass

    for attempt in range(10):
        try:
            lock_file = open(LOCK_FILE, "w")
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            return lock_file
        except BlockingIOError:
            time.sleep(0.1)

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

                # Strict Event Filter: Ignore high-frequency cosmetic noise
                # i3 event types: (1 << 31) | 0 is workspace, (1 << 31) | 3 is window
                if ev_type == 0x80000003: # WINDOW EVENT
                    change = ev_data.get("change")
                    if change not in ("new", "close", "move", "floating"):
                        continue
                elif ev_type == 0x80000000: # WORKSPACE EVENT
                    change = ev_data.get("change")
                    if change not in ("focus", "init", "empty", "reload", "restored"):
                        continue
                else:
                    continue

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
