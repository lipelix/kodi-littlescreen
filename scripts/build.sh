#!/usr/bin/env bash
# Package the add-on as an installable zip: dist/plugin.video.littlescreen-<version>.zip
set -euo pipefail
cd "$(dirname "$0")/.."
id=plugin.video.littlescreen
version=$(sed -n 's/.*<addon id="'"$id"'"[^>]* version="\([^"]*\)".*/\1/p' "$id/addon.xml")
[ -n "$version" ] || { echo "version not found in $id/addon.xml" >&2; exit 1; }
mkdir -p dist
out="dist/$id-$version.zip"
rm -f "$out"
zip -qr "$out" "$id" -x '*/__pycache__/*' '*.pyc' '*/.DS_Store'
echo "$out"
