#!/usr/bin/env bash
# Check the add-on on Kodi 20, 21 and 22, each headless in a Linux container (Docker):
# install the zip from build.sh, list profiles/categories/channels over JSON-RPC, play one
# video. Usage: scripts/check-kodi-versions.sh [VERSION...]  (default: 20 21 22)
# Results and Kodi logs: dist/kodi-check/kodi-<version>.{txt,log}
set -euo pipefail
cd "$(dirname "$0")/.."
versions=("$@")
[ ${#versions[@]} -gt 0 ] || versions=(20 21 22)
zip=$(./scripts/build.sh)
out=dist/kodi-check
mkdir -p "$out"
failed=()
for v in "${versions[@]}"; do
  echo "== Kodi $v"
  docker build -q -t "littlescreen-kodi:$v" -f "tests/kodi/Dockerfile.$v" tests/kodi >/dev/null
  cid=$(docker run -d --rm -v "$PWD:/src:ro" -e "ADDON_ZIP=/src/$zip" "littlescreen-kodi:$v")
  status=0
  docker exec "$cid" python3 /src/tests/kodi/check.py | tee "$out/kodi-$v.txt" || status=$?
  docker cp "$cid:/home/kodi/.kodi/temp/kodi.log" "$out/kodi-$v.log" >/dev/null 2>&1 || true
  docker stop -t 5 "$cid" >/dev/null
  [ "$status" -eq 0 ] || failed+=("$v")
done
if [ ${#failed[@]} -gt 0 ]; then
  echo "FAILED on Kodi ${failed[*]} (logs in $out)" >&2
  exit 1
fi
echo "All passed: Kodi ${versions[*]}"
