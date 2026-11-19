#!/usr/bin/env bash
# Take the README screenshots from a clean Kodi profile: headless Kodi in a Linux container
# (Docker, the image from check-kodi-versions.sh), English, default region, default add-on
# settings. Usage: scripts/screenshots.sh [VERSION]  (default: 21)
# Output: docs/screenshots/*.jpg (the PNGs from Kodi stay in dist/screenshots)
set -euo pipefail
cd "$(dirname "$0")/.."
v=${1:-21}
zip=$(./scripts/build.sh)
raw=dist/screenshots
rm -rf "$raw" && mkdir -p "$raw" docs/screenshots
docker build -q -t "littlescreen-kodi:$v" -f "tests/kodi/Dockerfile.$v" tests/kodi >/dev/null
cid=$(docker run -d --rm -v "$PWD:/src:ro" -e "ADDON_ZIP=/src/$zip" "littlescreen-kodi:$v")
trap 'docker stop -t 5 "$cid" >/dev/null' EXIT
docker exec -e DISPLAY=:99 "$cid" python3 /src/tests/kodi/screenshots.py /tmp/screenshots
docker cp "$cid:/tmp/screenshots/." "$raw/"
.venv/bin/python - "$raw" docs/screenshots <<'PY'
import pathlib, sys
from PIL import Image
raw, out = map(pathlib.Path, sys.argv[1:])
for png in sorted(raw.glob("*.png")):
    jpg = out / f"{png.stem}.jpg"
    Image.open(png).convert("RGB").save(jpg, quality=85, optimize=True, progressive=True)
    print(f"{jpg} ({jpg.stat().st_size // 1024} KB)")
PY
