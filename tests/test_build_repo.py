"""The Kodi repository tree built by scripts/build_repo.py."""

import hashlib
import importlib.util
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PAGES = "https://lipelix.github.io/kodi-littlescreen/"

spec = importlib.util.spec_from_file_location(
    "build_repo", os.path.join(ROOT, "scripts", "build_repo.py")
)
build_repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_repo)


def version_of(addon_id):
    return ET.parse(os.path.join(ROOT, addon_id, "addon.xml")).getroot().get("version")


def digest(path, algo):
    with open(path, "rb") as f:
        return hashlib.new(algo, f.read()).hexdigest()


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    return build_repo.build(ROOT, str(tmp_path_factory.mktemp("pages")))


def test_repository_addon_points_to_pages():
    root = ET.parse(os.path.join(ROOT, "repository.littlescreen", "addon.xml")).getroot()
    d = root.find("./extension[@point='xbmc.addon.repository']/dir")
    assert d.findtext("info") == PAGES + "addons.xml"
    assert d.findtext("checksum") == PAGES + "addons.xml.md5"
    assert d.findtext("datadir") == PAGES
    assert d.find("datadir").get("zip") == "true"
    assert d.findtext("hashes") == "sha256"


def test_addons_xml_lists_both_addons_with_checksum(tree):
    path = os.path.join(tree, "addons.xml")
    root = ET.parse(path).getroot()
    assert root.tag == "addons"
    assert {a.get("id"): a.get("version") for a in root} == {
        a: version_of(a) for a in build_repo.ADDONS
    }
    with open(path + ".md5") as f:
        assert f.read().strip() == digest(path, "md5")


@pytest.mark.parametrize("addon_id", build_repo.ADDONS)
def test_zip_per_addon(tree, addon_id):
    name = f"{addon_id}-{version_of(addon_id)}.zip"
    path = os.path.join(tree, addon_id, name)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    assert f"{addon_id}/addon.xml" in names
    assert all(n.startswith(addon_id + "/") for n in names)
    assert not [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".DS_Store"))]
    with open(path + ".sha256") as f:
        assert f.read().split() == [digest(path, "sha256"), name]


@pytest.mark.parametrize(
    "asset",
    [
        "plugin.video.littlescreen/resources/icon.png",
        "plugin.video.littlescreen/resources/fanart.jpg",
        "repository.littlescreen/icon.png",
        "repository.littlescreen/fanart.jpg",
    ],
)
def test_assets_next_to_zips(tree, asset):
    assert os.path.isfile(os.path.join(tree, asset))


def test_repository_zip_at_root_and_linked(tree):
    name = f"repository.littlescreen-{version_of('repository.littlescreen')}.zip"
    assert digest(os.path.join(tree, name), "sha256") == digest(
        os.path.join(tree, "repository.littlescreen", name), "sha256"
    )
    with open(os.path.join(tree, "index.html")) as f:
        assert f'href="{name}"' in f.read()


def test_every_folder_links_all_its_files(tree):
    # Kodi caches a browsed HTTP folder: a file not linked is "not found" afterwards.
    for dirpath, dirnames, filenames in os.walk(tree):
        with open(os.path.join(dirpath, "index.html")) as f:
            html = f.read()
        for name in [d + "/" for d in dirnames] + [n for n in filenames if n != "index.html"]:
            # exactly once, or Kodi lists the file twice
            assert html.count(f'<a href="{name}">{name}</a>') == 1, (dirpath, name)


def test_landing_page(tree):
    with open(os.path.join(tree, "index.html")) as f:
        html = f.read()
    repo_zip = f"repository.littlescreen-{version_of('repository.littlescreen')}.zip"
    assert f'class="button" href="{repo_zip}"' in html
    assert f"Version {version_of('plugin.video.littlescreen')}" in html
    assert "$" not in html  # every placeholder filled in
    # Kodi lists the links whose text equals the href: exactly the files, nothing else
    kodi_links = set(re.findall(r'<a href="([^"]+)">\1</a>', html))
    entries = {n + "/" if os.path.isdir(os.path.join(tree, n)) else n for n in os.listdir(tree)}
    assert kodi_links == entries - {"index.html"}
    # what the page shows is in the tree
    for src in re.findall(r'(?:src|href)="(plugin\.video\.littlescreen/[^"]+)"', html):
        assert os.path.isfile(os.path.join(tree, src)), src


def test_zips_are_reproducible(tree, tmp_path):
    again = build_repo.build(ROOT, str(tmp_path / "again"))
    for addon_id in build_repo.ADDONS:
        name = f"{addon_id}-{version_of(addon_id)}.zip"
        assert digest(os.path.join(tree, addon_id, name), "sha256") == digest(
            os.path.join(again, addon_id, name), "sha256"
        )


def test_refuses_to_empty_a_foreign_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(SystemExit):
        build_repo.build(ROOT, str(tmp_path))
    assert (tmp_path / "keep.txt").exists()


def test_version_bump_shows_in_the_tree(tmp_path):
    src = tmp_path / "src"
    for addon_id in build_repo.ADDONS:
        shutil.copytree(os.path.join(ROOT, addon_id), src / addon_id)
    xml = src / "plugin.video.littlescreen" / "addon.xml"
    old = version_of("plugin.video.littlescreen")
    xml.write_text(xml.read_text().replace(f'version="{old}"', 'version="99.0.0"', 1))
    out = build_repo.build(str(src), str(tmp_path / "out"))
    root = ET.parse(os.path.join(out, "addons.xml")).getroot()
    assert root.find("./addon[@id='plugin.video.littlescreen']").get("version") == "99.0.0"
    assert os.path.isfile(
        os.path.join(out, "plugin.video.littlescreen", "plugin.video.littlescreen-99.0.0.zip")
    )


def test_url_override_points_the_repository_elsewhere(tmp_path):
    out = build_repo.build(ROOT, str(tmp_path), "http://127.0.0.1:8765")
    name = f"repository.littlescreen-{version_of('repository.littlescreen')}.zip"
    with zipfile.ZipFile(os.path.join(out, name)) as zf:
        xml = zf.read("repository.littlescreen/addon.xml").decode()
    assert "http://127.0.0.1:8765/addons.xml.md5" in xml
    assert PAGES not in xml
    with open(os.path.join(out, "addons.xml")) as f:
        assert '<datadir zip="true">http://127.0.0.1:8765/</datadir>' in f.read()
