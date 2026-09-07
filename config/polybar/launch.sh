#!/usr/bin/env bash

# Terminate already running bar instances
killall -q polybar || true

# Wait until the processes have been shut down
while pgrep -u $UID -x polybar >/dev/null; do sleep 0.2; done

# Launch Polybar instances
nohup polybar apps >> /tmp/polybar-apps.log 2>&1 &
nohup polybar main >> /tmp/polybar.log 2>&1 &
