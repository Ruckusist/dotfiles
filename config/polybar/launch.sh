#!/usr/bin/env bash

# Terminate already running bar instances
killall -q polybar || true

# Wait until the processes have been shut down
while pgrep -u "$UID" -x polybar >/dev/null; do sleep 0.2; done

# Launch Polybar instances in a fully detached background session
python3 - << 'PYEOF'
import subprocess
import os
import sys

if os.fork() != 0:
    sys.exit(0)

os.setsid()

if os.fork() != 0:
    sys.exit(0)

f_apps = open("/tmp/polybar-apps.log", "a")
f_main = open("/tmp/polybar.log", "a")
f_right = open("/tmp/polybar-right.log", "a")

subprocess.Popen(["polybar", "apps"], stdout=f_apps, stderr=f_apps, start_new_session=True)
subprocess.Popen(["polybar", "main"], stdout=f_main, stderr=f_main, start_new_session=True)
subprocess.Popen(["polybar", "right"], stdout=f_right, stderr=f_right, start_new_session=True)
PYEOF
