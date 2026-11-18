from ytkids import videocache
from ytkids.catalog import Video


def test_remember_and_get(tmp_path):
    path = str(tmp_path / "v.json")
    videocache.VideoCache(path).remember([Video("abcdefghijk", "Paci paci", "Míša", "UC", 169)])
    assert videocache.VideoCache(path).get("abcdefghijk") == ("Paci paci", "Míša", 169)
    assert videocache.VideoCache(path).get("zzzzzzzzzzz") is None


def test_trims_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(videocache, "LIMIT", 2)
    cache = videocache.VideoCache(str(tmp_path / "v.json"))
    cache.remember([Video(f"id{n}", f"t{n}") for n in range(3)])
    assert list(cache.data) == ["id1", "id2"]


def test_broken_file_is_ignored(tmp_path):
    path = tmp_path / "v.json"
    path.write_text("[1, 2")
    assert videocache.VideoCache(str(path)).data == {}
