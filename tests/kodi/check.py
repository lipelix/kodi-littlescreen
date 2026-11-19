"""Check Little Screen inside a running headless Kodi (run in the container by
scripts/check-kodi-versions.sh).

Enables the unpacked add-ons, lists profiles, a profile's categories, a category (videos and
channel tiles) and a channel over JSON-RPC (TCP 9090), then starts the first video of the
category the way a click does (RunPlugin through the EventServer) and waits until it plays.
Prints one result line per step; exit code 1 when a step fails.
"""

import codecs
import glob
import json
import os
import re
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlparse

ADDON = "plugin.video.littlescreen"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME_ADDONS = os.path.expanduser("~/.kodi/addons")
KODI_LOG = os.path.expanduser("~/.kodi/temp/kodi.log")


class Rpc:
    """JSON-RPC over Kodi's raw TCP socket: a stream of JSON objects, notifications included."""

    def __init__(self, port=9090, wait=120):
        deadline = time.monotonic() + wait
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.buffer = ""
        self.last_id = 0

    def call(self, method, params=None, timeout=240):
        self.last_id += 1
        request = {"jsonrpc": "2.0", "id": self.last_id, "method": method, "params": params or {}}
        self.sock.sendall(json.dumps(request).encode())
        self.sock.settimeout(timeout)
        while True:
            message = self._next()
            if message.get("id") == self.last_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message["result"]

    def _next(self):
        parser = json.JSONDecoder()
        while True:
            text = self.buffer.lstrip()
            if text:
                try:
                    message, end = parser.raw_decode(text)
                    self.buffer = text[end:]
                    return message
                except json.JSONDecodeError:
                    pass
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("Kodi closed the JSON-RPC connection")
            self.buffer += self.decoder.decode(chunk)


def builtin(command):
    script = os.path.join(ROOT, "scripts", "kodi_builtin.py")
    subprocess.run([sys.executable, script, "127.0.0.1", command], check=True)


def wait_ready(rpc):
    for _ in range(120):
        try:
            if rpc.call("JSONRPC.Ping") == "pong":
                return
        except RuntimeError:
            pass
        time.sleep(1)
    raise TimeoutError("Kodi did not answer JSON-RPC")


def enable_addons(rpc):
    wanted = set(os.listdir(HOME_ADDONS)) | {"inputstream.adaptive"}
    for _ in range(10):
        disabled = {
            a["addonid"]
            for a in rpc.call("Addons.GetAddons", {"enabled": False}).get("addons", [])
            if a["addonid"] in wanted
        }
        if not disabled:
            return
        for addon_id in sorted(disabled):
            try:
                rpc.call("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
            except RuntimeError:
                pass  # a dependency is still off; next round
        time.sleep(2)
    raise RuntimeError(f"cannot enable: {sorted(disabled)}")


def listing(rpc, url):
    result = rpc.call(
        "Files.GetDirectory",
        {"directory": url, "media": "video", "properties": ["title", "art"]},
    )
    return result.get("files") or []


def params(url):
    return dict(parse_qsl(urlparse(url).query))


def play(rpc, item):
    builtin(f'RunPlugin("{item["file"]}")')
    started = None
    for _ in range(120):
        time.sleep(1)
        players = [p for p in rpc.call("Player.GetActivePlayers") if p["type"] == "video"]
        if not players:
            continue
        pid = players[0]["playerid"]
        props = rpc.call("Player.GetProperties", {"playerid": pid, "properties": ["time", "speed"]})
        t = props["time"]
        seconds = t["hours"] * 3600 + t["minutes"] * 60 + t["seconds"]
        if started is None and seconds > 0:
            started = seconds
        if started is not None and seconds >= started + 3:
            title = rpc.call("Player.GetItem", {"playerid": pid, "properties": ["title"]})
            queue = rpc.call("Playlist.GetItems", {"playlistid": 1}).get("limits", {})
            rpc.call("Player.Stop", {"playerid": pid})
            return title["item"].get("title") or title["item"].get("label"), queue.get("total")
    raise TimeoutError("no video played for 3 s within 2 minutes")


def python_api():
    """xbmc.python is not listed over JSON-RPC: read its addon.xml in Kodi's system folder."""
    for path in glob.glob("/usr/share/kodi/addons/xbmc.python/addon.xml"):
        return ET.parse(path).getroot().get("version")
    return "unknown"


def log_errors():
    """Kodi log entries (a timestamped line and its indented continuation) that are errors
    or tracebacks and mention this add-on; other add-ons' first-run noise is left out."""
    if not os.path.exists(KODI_LOG):
        return []
    with open(KODI_LOG, encoding="utf-8", errors="replace") as log:
        entries = re.split(r"\n(?=\d{4}-\d\d-\d\d )", log.read())
    return [
        entry.splitlines()[0]
        for entry in entries
        if "littlescreen" in entry and (" error " in entry or "Traceback" in entry)
    ]


def main():
    results = []

    def step(name, ok, detail):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)

    rpc = Rpc()
    wait_ready(rpc)
    app = rpc.call("Application.GetProperties", {"properties": ["version"]})["version"]
    version = f"{app['major']}.{app['minor']}"
    if app["tag"] != "stable":
        version += f" {app['tag']} {app.get('tagversion', '')}".rstrip()
    print(f"Kodi {version}, xbmc.python {python_api()}", flush=True)

    enable_addons(rpc)
    details = rpc.call(
        "Addons.GetAddonDetails",
        {"addonid": ADDON, "properties": ["version", "enabled", "dependencies"]},
    )["addon"]
    youtube = rpc.call(
        "Addons.GetAddonDetails", {"addonid": "plugin.video.youtube", "properties": ["version"]}
    )["addon"]
    step(
        "install",
        details["enabled"],
        f"{ADDON} {details['version']}, plugin.video.youtube {youtube['version']}",
    )

    try:
        profiles = listing(rpc, f"plugin://{ADDON}/")
        step("profiles", len(profiles) >= 1, ", ".join(p["label"] for p in profiles))
        categories = listing(rpc, profiles[0]["file"])
        categories = [c for c in categories if params(c["file"]).get("action") == "category"]
        step("categories", len(categories) >= 3, ", ".join(c["label"] for c in categories))
        items = listing(rpc, categories[0]["file"])
        videos = [i for i in items if params(i["file"]).get("action") == "play"]
        channels = [i for i in items if params(i["file"]).get("action") == "channel"]
        step(
            "category",
            len(videos) >= 5,
            f"{categories[0]['label']}: {len(videos)} videos, {len(channels)} channel tiles",
        )
        if channels:
            channel_items = listing(rpc, channels[0]["file"])
            channel_videos = [i for i in channel_items if params(i["file"]).get("action") == "play"]
            step(
                "channel",
                len(channel_videos) >= 1,
                f"{channels[0]['label']}: {len(channel_videos)} videos",
            )
        title, queued = play(rpc, videos[0])
        step("play", True, f"{title!r} played, {queued} videos in the playlist")
    except (RuntimeError, TimeoutError, IndexError, OSError) as err:
        step("listing/playback", False, str(err))

    errors = log_errors()
    step("log", not errors, f"{len(errors)} error lines" + "".join(f"\n  {e}" for e in errors[:10]))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
