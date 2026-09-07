#!/usr/bin/env bash

# Check if transmission is running
if ! systemctl is-active --quiet transmission-daemon; then
    echo ""
    exit 0
fi

# Get list of torrents
torrent_info=$(transmission-remote -l 2>/dev/null)

# Check if there's any active downloads
if echo "$torrent_info" | grep -q "None"; then
    # No torrents
    echo " --"
    exit 0
fi

# Extract the sum line at the bottom
summary=$(echo "$torrent_info" | tail -n 1)

# Extract download/upload rates
dl_speed=$(echo "$summary" | awk '{print $4}')
ul_speed=$(echo "$summary" | awk '{print $3}')

# If transmission returns 'Sum:', the next fields are speeds.
# Sometimes parsing differs slightly. Let's do a reliable total extraction:
dl_speed=$(transmission-remote -st | grep "Download Speed" | awk '{print $3 " " $4}')

# Just count how many are active vs downloading
total=$(echo "$torrent_info" | wc -l)
real_total=$((total - 2)) # Remove header and footer

# Return format for Polybar
if [[ "$dl_speed" == "0.0 "* ]]; then
    echo " $real_total"
else
    echo " $real_total  $dl_speed"
fi