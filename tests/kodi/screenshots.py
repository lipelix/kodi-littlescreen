"""Take the README screenshots inside a running headless Kodi (run in the container by
scripts/screenshots.sh).

A clean profile: Kodi in English with its default region, the add-on with default settings
(profile 1: ages 4 and under, big pictures; profile 2: ages 5 to 8, list with search).
Opens each listing in the Videos window through the EventServer and saves the X display
(xgrab.py; Kodi's own TakeScreenshot crashes under Xvfb). GUI sounds are turned off first:
Kodi in the container has no audio device and crashed on a navigation sound.
Usage: screenshots.py OUT_DIR  (with DISPLAY set to Kodi's X display)
"""

import os
import sys
import time

import xgrab
from check import ADDON, Rpc, builtin, enable_addons, listing, params, wait_ready

SETTLE = 8  # seconds for thumbnails to load and the view mode to stick


def wait_folder(rpc, url, wait=120):
    """Wait until the Videos window shows `url` (Kodi reorders query parameters)."""
    want = params(url)
    for _ in range(wait):
        time.sleep(1)
        labels = rpc.call("XBMC.GetInfoLabels", {"labels": ["Container.FolderPath"]})
        path = labels["Container.FolderPath"]
        if path.startswith(f"plugin://{ADDON}/") and params(path) == want:
            return
    raise TimeoutError(f"Kodi did not open {url}")


def shot(rpc, out, name, url):
    builtin(f'ActivateWindow(Videos,"{url}",return)')
    wait_folder(rpc, url)
    time.sleep(SETTLE)
    xgrab.save(os.path.join(out, f"{name}.png"))
    print(f"saved {name}.png: {url}", flush=True)


def prepare(rpc):
    """No GUI sounds, no ".." item, and the start-up "enable this add-on?" dialogs closed."""
    for setting, value in (("lookandfeel.soundskin", ""), ("filelists.showparentdiritems", False)):
        rpc.call("Settings.SetSettingValue", {"setting": setting, "value": value})
    for _ in range(10):
        labels = rpc.call("XBMC.GetInfoLabels", {"labels": ["System.HasModalDialog"]})
        if labels["System.HasModalDialog"] != "true" and not _yesno_open(rpc):
            return
        rpc.call("Input.Back")
        time.sleep(1.5)
    raise RuntimeError("a dialog stays open")


def _yesno_open(rpc):
    labels = rpc.call("XBMC.GetInfoLabels", {"labels": ["System.CurrentWindow"]})
    return labels["System.CurrentWindow"] == "Yes / No dialog"


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rpc = Rpc()
    wait_ready(rpc)
    time.sleep(3)  # the start-up dialogs open a moment after JSON-RPC answers
    enable_addons(rpc)
    prepare(rpc)
    time.sleep(SETTLE)  # let start-up notifications fade

    root = f"plugin://{ADDON}/"
    profiles = listing(rpc, root)
    toddler, older = profiles[0]["file"], profiles[1]["file"]
    search = f"{root}?action=search&p={params(older)['p']}&q=dinosaurs"

    shot(rpc, out, "profiles", root)
    shot(rpc, out, "big-pictures", shows(rpc, toddler))
    shot(rpc, out, "list", shows(rpc, older))
    shot(rpc, out, "search", search)


def shows(rpc, home):
    """The "Shows" category of a profile (the first one when the name differs)."""
    categories = [c for c in listing(rpc, home) if params(c["file"]).get("action") == "category"]
    named = [c for c in categories if c["label"] == "Shows"]
    return (named or categories)[0]["file"]


if __name__ == "__main__":
    main()
