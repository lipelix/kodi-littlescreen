#!/bin/sh
# Start a headless Kodi: Xvfb display, the add-on zip from $ADDON_ZIP unpacked into the
# profile, Kodi in the foreground. JSON-RPC (TCP 9090) and the EventServer (UDP 9777)
# listen on localhost by default; check.py drives Kodi through them.
set -eu
[ -n "${ADDON_ZIP:-}" ] || { echo "Missing required environment variable: ADDON_ZIP" >&2; exit 1; }
mkdir -p "$HOME/.kodi/addons"
python3 -m zipfile -e "$ADDON_ZIP" "$HOME/.kodi/addons/"
Xvfb :99 -screen 0 1280x720x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99
i=0
while [ ! -e /tmp/.X11-unix/X99 ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i + 1)); done
exec kodi --windowing=x11
