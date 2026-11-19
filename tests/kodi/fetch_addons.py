"""Download add-ons and their dependencies from the official Kodi repository.

Usage: fetch_addons.py BRANCH ADDON_ID... (BRANCH: nexus, omega, piers, ...)

Unpacks each add-on into ~/.kodi/addons, skipping what Kodi itself provides (xbmc.*,
kodi.*, add-ons already in Kodi's system folders such as a packaged inputstream.adaptive).
Runs at image build time, so a test Kodi does not depend on its own add-on installer.
"""

import glob
import gzip
import hashlib
import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

# mirrors.kodi.tv redirects to a mirror near the caller, which some networks cannot reach
MIRRORS = (
    "https://mirrors.kodi.tv/addons",
    "https://ftp.fau.de/xbmc/addons",
    "https://ftp.hosteurope.de/mirror/xbmc.org/addons",
)
SYSTEM_DIRS = ("/usr/share/kodi/addons", "/usr/lib/*/kodi/addons", "/usr/lib*/kodi/addons")
HOME_ADDONS = os.path.expanduser("~/.kodi/addons")


def get(path):
    errors = []
    for base in MIRRORS:
        try:
            with urllib.request.urlopen(f"{base}/{path}", timeout=30) as response:
                return response.read()
        except OSError as err:
            errors.append(f"{base}: {err}")
    raise OSError(f"cannot download {path}: " + "; ".join(errors))


def system_addons():
    found = set()
    for pattern in SYSTEM_DIRS:
        for folder in glob.glob(pattern):
            found.update(os.listdir(folder))
    return found


def main():
    branch, wanted = sys.argv[1], sys.argv[2:]
    index = ET.fromstring(gzip.decompress(get(f"{branch}/addons.xml.gz")))
    catalogue = {a.get("id"): a for a in index.iter("addon")}
    provided = system_addons()
    todo, done = list(wanted), set()
    while todo:
        addon_id = todo.pop()
        if addon_id in done or addon_id in provided or addon_id.startswith(("xbmc.", "kodi.")):
            continue
        done.add(addon_id)
        addon = catalogue.get(addon_id)
        if addon is None:
            raise SystemExit(f"{addon_id} is not in the {branch} repository")
        version = addon.get("version")
        name = f"{branch}/{addon_id}/{addon_id}-{version}.zip"
        data = get(name)
        expected = get(f"{name}.sha256").decode().split()[0]
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f"checksum mismatch: {name}")
        zipfile.ZipFile(io.BytesIO(data)).extractall(HOME_ADDONS)
        print(f"{addon_id} {version}")
        for dep in addon.iter("import"):
            if dep.get("optional") != "true":
                todo.append(dep.get("addon"))


if __name__ == "__main__":
    main()
