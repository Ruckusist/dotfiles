#!/usr/bin/env python3
"""
i3-single-center.py
Dynamically centers single-window workspaces on ultrawide displays in i3wm.

- 1 tiled window (or empty workspace): sets horizontal outer gaps so the window
  is exactly 50% width, centered directly under Polybar.
- 2+ tiled windows: resets horizontal outer gaps to default (2px) so windows
  tile across the full width of the screen using standard i3 logic.
- Maintains top gap (46px) so Polybar is never covered.
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

def count_tiled_windows(node):
    if node.get("window"):
        return 1
    count = 0
    # Search tiled children (nodes), ignoring floating_nodes
    for child in node.get("nodes", []):
        count += count_tiled_windows(child)
    return count

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

def update_current_workspace_gaps(ipc):
    tree = ipc.send_cmd(4) # GET_TREE
    if not tree:
        return

    ws = find_focused_workspace(tree)
    if not ws:
        return

    ws_name = ws.get("name")
    if ws_name == "__i3_scratch":
        return

    tiled_count = count_tiled_windows(ws)

    output_node = find_workspace_output(tree, ws_name)
    output_width = 3440
    if output_node and "rect" in output_node:
        output_width = output_node["rect"]["width"]

    # Target 50% width centered
    single_gap = int((output_width * 0.25) - INNER_GAP)
    target_gap = single_gap if tiled_count <= 1 else DEFAULT_OUTER_GAP

    current_gaps = ws.get("gaps", {})
    current_outer_h = current_gaps.get("right", 0) + DEFAULT_OUTER_GAP

    if abs(current_outer_h - target_gap) > 5:
        ipc.send_cmd(0, f"gaps horizontal current set {target_gap}; gaps top current set {TOP_GAP}")

def acquire_lock():
    # If another instance exists, terminate it to take over
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
    lock_file = acquire_lock()

    running = True
    def sig_handler(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    while running:
        try:
            sock_path = get_socket_path()
            ipc = I3IPC(sock_path)
            if not ipc.subscribe(["workspace", "window"]):
                time.sleep(1)
                continue

            update_current_workspace_gaps(ipc)

            while running:
                r, _, _ = select.select([ipc.ev_sock], [], [], 0.5)
                if not r:
                    continue

                ev_type, ev_data = ipc.recv_event()
                if ev_data is None:
                    # Broken connection (i3 reload/restart)
                    break

                # Drain burst events within 20ms
                while True:
                    r_drain, _, _ = select.select([ipc.ev_sock], [], [], 0.02)
                    if not r_drain:
                        break
                    _, extra = ipc.recv_event()
                    if extra is None:
                        break

                update_current_workspace_gaps(ipc)

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
