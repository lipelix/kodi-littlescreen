"""Build the Kodi repository tree served on GitHub Pages.

    .venv/bin/python scripts/build_repo.py [--src DIR] [--out DIR] [--url URL]

Writes into OUT (default dist/pages, emptied first):

    addons.xml, addons.xml.md5                   the index Kodi reads (info, checksum)
    <id>/<id>-<version>.zip (+ .sha256)          each add-on (datadir, hashes)
    <id>/<assets>                                icon/fanart shown before installing
    repository.littlescreen-<version>.zip        the repository add-on, for "Install from zip"
    screenshots/*.jpg                            docs/screenshots, shown on the landing page
    index.html (in every folder)                 links to all files: Kodi's file manager
                                                 browses the folders by them (GitHub Pages
                                                 has no directory listing); the root one is
                                                 the landing page (scripts/landing.html)

Zips are reproducible: sorted entries, fixed timestamps, no caches.
--url serves the tree from somewhere else than GitHub Pages (e.g. http://127.0.0.1:8765/ to
test it with a local Kodi): the repository add-on in the tree then points there.
"""

import argparse
import hashlib
import os
import shutil
import string
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ADDONS = ("plugin.video.littlescreen", "repository.littlescreen")
REPOSITORY = "repository.littlescreen"
PAGES_URL = "https://lipelix.github.io/kodi-littlescreen/"
LANDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing.html")
PLUGIN = "plugin.video.littlescreen"
SCREENSHOTS = os.path.join("docs", "screenshots")
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo")
ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def addon_xml(src, addon_id, url):
    """addon.xml as published: the repository add-on points to URL."""
    with open(os.path.join(src, addon_id, "addon.xml"), encoding="utf-8") as f:
        text = f.read()
    if addon_id == REPOSITORY and url != PAGES_URL:
        if PAGES_URL not in text:
            raise SystemExit(f"{addon_id}/addon.xml does not point to {PAGES_URL}")
        text = text.replace(PAGES_URL, url)
    return text


def read_addon(src, addon_id, url):
    """Return (version, addon.xml text without the XML declaration, asset paths)."""
    path = os.path.join(src, addon_id, "addon.xml")
    text = addon_xml(src, addon_id, url)
    root = ET.fromstring(text.encode("utf-8"))
    if root.get("id") != addon_id:
        raise SystemExit(f"{path}: id is {root.get('id')!r}, expected {addon_id!r}")
    version = root.get("version")
    if not version:
        raise SystemExit(f"{path}: no version")
    if text.startswith("<?xml"):
        text = text[text.index("?>") + 2 :]
    assets = [
        el.text.strip()
        for el in root.iterfind("./extension[@point='xbmc.addon.metadata']/assets/*")
        if el.text and el.text.strip()
    ]
    return version, text.strip(), assets


def files_of(folder):
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for name in sorted(filenames):
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIXES):
                continue
            yield os.path.join(dirpath, name)


def make_zip(src, addon_id, out_path, url):
    folder = os.path.join(src, addon_id)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files_of(folder):
            rel = os.path.relpath(path, folder)
            info = zipfile.ZipInfo(os.path.join(addon_id, rel).replace(os.sep, "/"), ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            if rel == "addon.xml":
                data = addon_xml(src, addon_id, url).encode("utf-8")
            else:
                with open(path, "rb") as f:
                    data = f.read()
            zf.writestr(info, data)


def file_hash(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def listing(folder):
    """Links to everything in FOLDER, folders with a trailing slash.

    Kodi reads an HTTP folder by its links and keeps only those whose text equals the
    href, so other links on the page do not show up in Kodi. It caches what it read: a
    file missing here is "not found" for the rest of the session, so after "Install from
    zip" on this folder the repository could not read addons.xml.md5 until Kodi restarted.
    """
    names = []
    for name in sorted(os.listdir(folder)):
        if name == "index.html":
            continue
        names.append(name + "/" if os.path.isdir(os.path.join(folder, name)) else name)
    return "\n".join(f'<li><a href="{n}">{n}</a></li>' for n in names)


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""


def landing(files, repo_zip, version):
    """The root index.html: the landing page around the list of files.

    Its other links have a text that differs from their href, so Kodi ignores them.
    """
    with open(LANDING, encoding="utf-8") as f:
        template = string.Template(f.read())
    return template.substitute(files=files, repo_zip=repo_zip, version=version)


def write_indexes(out, repo_zip, version):
    """index.html in every folder (GitHub Pages has no directory listing)."""
    for dirpath, _dirnames, _filenames in os.walk(out):
        rel = os.path.relpath(dirpath, out).replace(os.sep, "/")
        if rel == ".":
            write(os.path.join(dirpath, "index.html"), landing(listing(dirpath), repo_zip, version))
            continue
        body = f"<h1>{rel}/</h1>\n<ul>\n{listing(dirpath)}\n</ul>"
        write(os.path.join(dirpath, "index.html"), page(f"Little Screen: {rel}/", body))


def clean_out(out):
    if os.path.isdir(out) and os.listdir(out):
        if not os.path.exists(os.path.join(out, "addons.xml")):
            raise SystemExit(f"{out} is not empty and has no addons.xml; not deleting it")
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)


def build(src, out, url=PAGES_URL):
    if not url.endswith("/"):
        url += "/"
    clean_out(out)
    entries = []
    repo_zip = None
    versions = {}
    for addon_id in ADDONS:
        version, xml, assets = read_addon(src, addon_id, url)
        versions[addon_id] = version
        entries.append(xml)
        target = os.path.join(out, addon_id)
        os.makedirs(target)
        zip_name = f"{addon_id}-{version}.zip"
        zip_path = os.path.join(target, zip_name)
        make_zip(src, addon_id, zip_path, url)
        write(zip_path + ".sha256", f"{file_hash(zip_path, 'sha256')}  {zip_name}\n")
        for asset in assets:
            dest = os.path.join(target, asset)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(src, addon_id, asset), dest)
        if addon_id == REPOSITORY:
            repo_zip = zip_name
            shutil.copyfile(zip_path, os.path.join(out, zip_name))
    addons_xml = os.path.join(out, "addons.xml")
    write(
        addons_xml,
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
        + "\n".join(entries)
        + "\n</addons>\n",
    )
    write(addons_xml + ".md5", file_hash(addons_xml, "md5") + "\n")
    screenshots = os.path.join(src, SCREENSHOTS)
    if os.path.isdir(screenshots):
        shutil.copytree(screenshots, os.path.join(out, "screenshots"))
    write_indexes(out, repo_zip, versions[PLUGIN])
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", default=ROOT, help="folder with the add-on folders")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist", "pages"))
    parser.add_argument("--url", default=PAGES_URL, help="where the tree is served")
    args = parser.parse_args(argv)
    print(build(args.src, args.out, args.url))


if __name__ == "__main__":
    sys.exit(main())
