#!/usr/bin/env bash
# Install the working copy into the Kodi on this machine (macOS) and enable it.
# Needs Kodi's web server (JSON-RPC, port 8080) and EventServer (UDP 9777) turned on.
set -euo pipefail
cd "$(dirname "$0")/.."
id=plugin.video.littlescreen
kodi_home="$HOME/Library/Application Support/Kodi"
host=127.0.0.1
[ -d "$kodi_home/addons" ] || { echo "Kodi addons dir not found: $kodi_home/addons" >&2; exit 1; }
rsync -a --delete --exclude __pycache__ --exclude '*.pyc' "$id/" "$kodi_home/addons/$id/"
python3 scripts/kodi_builtin.py "$host" UpdateLocalAddons
sleep 2
rpc() { curl -fsS -m 5 -H 'Content-Type: application/json' -d "$1" "http://$host:8080/jsonrpc"; echo; }
rpc '{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"'"$id"'","enabled":true}}'
rpc '{"jsonrpc":"2.0","id":2,"method":"Addons.GetAddonDetails","params":{"addonid":"'"$id"'","properties":["version","enabled"]}}'
