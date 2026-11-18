import os
from urllib.parse import parse_qsl, urlparse

import pytest

import kodistub
from littlescreen import plugin
from littlescreen.innertube import InnerTubeError
from test_profiles import DEFAULTS

ADDON = os.path.join(os.path.dirname(__file__), "..", "plugin.video.littlescreen")
BASE = "plugin://plugin.video.littlescreen/"
SETTINGS = {**DEFAULTS, "hl": "cs", "gl": "CZ", "video_language": 0}
CZECH_ONLY = {**SETTINGS, "video_language": 2}


@pytest.fixture
def kodi(tmp_path, fixture, monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, age_group, hl, gl, cache_file):
            self.age_group = age_group

        def home(self, params=None):
            calls.append(("home", self.age_group, params))
            return fixture("home_music.json" if params else "home_preschool.json")

        def client_version(self):
            return "2.0"

        def channel(self, channel_id):
            calls.append(("channel", channel_id))
            return fixture("channel.json")

        def continuation(self, token):
            calls.append(("continuation", token))
            return fixture("channel_continuation.json")

        def search(self, query):
            calls.append(("search", query))
            return fixture("search.json")

        def search_continuation(self, token):
            calls.append(("search_continuation", token))
            return fixture("search.json")

    monkeypatch.setattr(plugin, "KidsClient", FakeClient)

    def run(query="", settings=None, keyboard=None, skin="skin.estuary", shown=True):
        kodistub.reset(
            settings or SETTINGS,
            ADDON,
            str(tmp_path),
            skin=skin,
            keyboard=keyboard,
            folder_path=BASE + query if shown else None,
        )
        plugin.run([BASE, "1", query])
        return kodistub.STATE

    run.calls = calls
    return run


def query(url):
    return dict(parse_qsl(urlparse(url).query))


def test_start_lists_profiles_as_wall(kodi):
    state = kodi()
    labels = [item.label for _, item, _ in state["items"]]
    assert labels == ["Batole", "#2"]
    assert query(state["items"][0][0]) == {"action": "home", "p": "1"}
    assert state["items"][0][1].art["thumb"].endswith("profile_preschool.png")
    assert state["builtins"] == ["Container.SetViewMode(500)"]
    assert state["category"] == "#30035"


def test_single_profile_opens_home_directly(kodi):
    state = kodi(settings={**SETTINGS, "profile2.enabled": False})
    labels = [item.label for _, item, _ in state["items"]]
    assert labels == ["Pořady", "Hudba", "Výuka", "Objevování"]


def test_no_profile_opens_settings(kodi):
    state = kodi(settings={**SETTINGS, "profile1.enabled": False, "profile2.enabled": False})
    assert state["opened_settings"] and state["ended"] is False


def test_toddler_home_has_no_search(kodi):
    state = kodi("?action=home&p=1")
    labels = [item.label for _, item, _ in state["items"]]
    assert "#30030" not in labels
    assert state["items"][1][1].art["thumb"].endswith("category_music.png")
    assert kodi.calls[-1] == ("home", "PRESCHOOL", None)


def test_list_profile_home_has_search_and_widelist(kodi):
    state = kodi("?action=home&p=2")
    labels = [item.label for _, item, _ in state["items"]]
    assert labels[-1] == "#30030"
    assert state["builtins"] == ["Container.SetViewMode(55)"]
    assert kodi.calls[-1] == ("home", "YOUNGER", None)


def test_category_lists_playable_videos_via_youtube_addon(kodi):
    state = kodi("?action=category&p=1&c=kgQCCAM%253D")
    assert ("home", "PRESCHOOL", "kgQCCAM%3D") in kodi.calls
    url, item, is_folder = state["items"][0]
    assert url.startswith("plugin://plugin.video.youtube/play/?video_id=")
    assert not is_folder and item.props["IsPlayable"] == "true"
    assert item.tag.data["duration"] > 0
    assert "plot" not in item.tag.data  # toddlers get no text besides the title
    assert state["content"] == "videos" and state["category"] == "Hudba"


def test_channels_open_as_folders(kodi):
    state = kodi("?action=category&p=2&c=kgQCCAM%253D")
    folders = [(url, item) for url, item, is_folder in state["items"] if is_folder]
    assert folders
    assert query(folders[0][0])["action"] == "channel"
    videos = [item for _, item, is_folder in state["items"] if not is_folder]
    assert videos[0].tag.data["plot"]


def test_channel_has_more_item(kodi):
    state = kodi("?action=channel&p=1&id=UC3P5fGCWhACNd54AwY-EyQQ")
    url, item, _ = state["items"][-1]
    assert item.label == "#30031"
    more = query(url)
    assert more["action"] == "more" and more["kind"] == "browse" and more["t"]
    state = kodi("?" + url.split("?", 1)[1])
    assert kodi.calls[-1][0] == "continuation"
    assert len(state["items"]) == 101


def test_search_item_is_an_action_not_a_folder(kodi):
    state = kodi("?action=home&p=2")
    url, item, is_folder = state["items"][-1]
    assert item.label == "#30030" and not is_folder
    assert query(url) == {"action": "ask", "p": "2"}


def test_search_asks_then_updates_container(kodi):
    state = kodi("?action=ask&p=2", keyboard="krtek")
    assert state["ended"] is None  # RunPlugin: no listing to end
    assert state["builtins"][0].startswith("Container.Update(")
    target = state["builtins"][0][len("Container.Update(") : -1]
    assert query(target) == {"action": "search", "p": "2", "q": "krtek"}
    state = kodi("?" + target.split("?", 1)[1])
    assert kodi.calls[-1] == ("search", "krtek")
    assert query(state["items"][-1][0])["kind"] == "search"


def test_search_cancelled(kodi):
    state = kodi("?action=ask&p=2", keyboard=None)
    assert state["ended"] is None and state["builtins"] == []


def test_search_refused_for_toddler(kodi):
    with pytest.raises(ValueError):
        kodi("?action=search&p=1&q=x")
    with pytest.raises(ValueError):
        kodi("?action=ask&p=1")


def test_api_failure_notifies(kodi, monkeypatch):
    def boom(self, params=None):
        raise InnerTubeError("HTTP 500")

    monkeypatch.setattr(plugin.KidsClient, "home", boom)
    state = kodi("?action=home&p=1")
    assert state["notifications"] == ["#30032"] and state["ended"] is False


def test_disabled_profile_falls_back_to_start(kodi):
    state = kodi("?action=home&p=3")
    assert [item.label for _, item, _ in state["items"]] == ["Batole", "#2"]


def test_other_skin_keeps_view(kodi):
    state = kodi(skin="skin.arctic.zephyr")
    assert state["builtins"] == []


def test_view_waits_for_kodi_to_show_the_listing(kodi):
    state = kodi("?action=home&p=1", shown=False)
    assert state["builtins"] == []
    assert state["slept"] == 3000
    state = kodi("?action=home&p=1")
    assert state["builtins"] == ["Container.SetViewMode(500)"]
    assert "slept" not in state


def test_same_listing_ignores_parameter_order():
    a = "plugin://plugin.video.littlescreen/?action=category&c=kgQCCAM%253D&p=1"
    b = "plugin://plugin.video.littlescreen/?action=category&p=1&c=kgQCCAM%253D"
    assert plugin.same_listing(a, b)
    assert not plugin.same_listing(a, b.replace("p=1", "p=2"))


def labels(state):
    return [item.label for _, item, _ in state["items"]]


def test_czech_only_hides_slovak_videos(kodi):
    everything = labels(kodi("?action=category&p=2&c=kgQCCAM%253D"))
    czech = labels(kodi("?action=category&p=2&c=kgQCCAM%253D", settings=CZECH_ONLY))
    slovak = "Keď si šťastný | Slovenské detské pesničky | Keď si šťastný"
    assert slovak in everything and slovak not in czech
    assert "Míša Růžičková - Paci paci - Písničky pro děti" in czech
    assert 0 < len(czech) < len(everything)


def test_filtered_page_is_topped_up_from_next_pages(kodi, monkeypatch):
    slovak = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    {
                        "itemSectionRenderer": {
                            "contents": [
                                {
                                    "compactVideoRenderer": {
                                        "videoId": "sk1",
                                        "title": {
                                            "runs": [{"text": "Rozprávka pre deti po slovensky"}]
                                        },
                                    }
                                },
                            ],
                            "continuations": [{"nextContinuationData": {"continuation": "NEXT"}}],
                        }
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(plugin.KidsClient, "channel", lambda self, cid: slovak)
    state = kodi("?action=channel&p=2&id=UCsk", settings=CZECH_ONLY)
    assert kodi.calls[-1] == ("continuation", "NEXT")
    assert "Rozprávka pre deti po slovensky" not in labels(state)
    assert len(state["items"]) > 12


def test_channel_memory_is_saved(kodi, tmp_path):
    kodi("?action=category&p=2&c=kgQCCAM%253D", settings=CZECH_ONLY)
    assert (tmp_path / "channels.json").exists()


SMEJKO = "UCia0mF-pM9xo5ZMN8DoFp_Q"
DOROTKA = "UCGnLFnCvL4InZX3EYSQ_d6w"

SLOVAK_TITLE = "Pesničky a rozprávky pre deti po slovensky"


def test_unclear_channels_are_looked_up_once(kodi, fixture, monkeypatch):
    slovak_page = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    {
                        "itemSectionRenderer": {
                            "contents": [
                                {
                                    "compactVideoRenderer": {
                                        "videoId": f"s{n}",
                                        "title": {"runs": [{"text": SLOVAK_TITLE}]},
                                    }
                                }
                                for n in range(3)
                            ]
                        }
                    }
                ]
            }
        }
    }
    probed = []

    def channel(self, channel_id):
        probed.append(channel_id)
        return slovak_page if channel_id in (SMEJKO, DOROTKA) else fixture("channel.json")

    monkeypatch.setattr(plugin.KidsClient, "channel", channel)
    state = kodi("?action=category&p=1&c=kgQCCAM%253D", settings=CZECH_ONLY)
    shown = labels(state)
    assert SMEJKO in probed and DOROTKA in probed
    assert "Smejko a Tanculienka - Benny" not in shown
    assert not any("POTAMUS" in label for label in shown)
    assert "Míša Růžičková - Paci paci - Písničky pro děti" in shown
    probed.clear()
    kodi("?action=category&p=1&c=kgQCCAM%253D", settings=CZECH_ONLY)
    assert probed == []  # remembered in channels.json


EMPTY = "UCK8NIOLI5IT-cbGdd_cK79Q"  # Kristýna Krčmová
HANICKA = "UCKvSNKq94qWHL_OWDDC68lg"
CIPERKOVE = "UCVGHomAxlCzmBH7T5SN0_ag"  # channel tiles YouTube sends itself
API_TILES = {CIPERKOVE, "UCWaYP51K6ayGFNZ9j5TdjoA"}


def tiles(state):
    return [
        (item.label, query(url)["id"], item.art["thumb"])
        for url, item, is_folder in state["items"]
        if is_folder and query(url).get("action") == "channel"
    ]


def test_category_ends_with_tiles_of_its_czech_channels(kodi, fixture, monkeypatch):
    empty = {"contents": {"sectionListRenderer": {"contents": []}}}
    slovak = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    {
                        "itemSectionRenderer": {
                            "contents": [
                                {
                                    "compactVideoRenderer": {
                                        "videoId": f"s{n}",
                                        "title": {"runs": [{"text": SLOVAK_TITLE}]},
                                    }
                                }
                                for n in range(3)
                            ]
                        }
                    }
                ]
            }
        }
    }
    looked_up = []

    def channel(self, channel_id):
        looked_up.append(channel_id)
        if channel_id == EMPTY:
            return empty
        if channel_id in (SMEJKO, DOROTKA, HANICKA):
            return slovak
        return fixture("channel.json")

    monkeypatch.setattr(plugin.KidsClient, "channel", channel)
    state = kodi("?action=category&p=1&c=kgQCCAM%253D", settings=CZECH_ONLY)
    found = tiles(state)
    names = [name for name, _, _ in found]
    ids = [cid for _, cid, _ in found]
    assert "Písničky pro děti" in names and "BibiBum" in names
    assert EMPTY not in ids  # no videos in YouTube Kids
    assert SMEJKO not in ids and HANICKA not in ids  # Slovak channels
    assert len(ids) == len(set(ids))
    assert ids.count(CIPERKOVE) == 1  # not added twice
    derived = [thumb for _, cid, thumb in found if cid not in API_TILES]
    assert derived and all(t.startswith("https://i.ytimg.com/vi/") for t in derived)
    # Tiles come after the videos and before nothing else.
    kinds = [is_folder for _, _, is_folder in state["items"]]
    assert kinds == sorted(kinds)
    looked_up.clear()
    again = kodi("?action=category&p=1&c=kgQCCAM%253D", settings=CZECH_ONLY)
    assert looked_up == [] and tiles(again) == found


def test_channel_pages_do_not_get_tiles(kodi):
    state = kodi("?action=channel&p=1&id=UC3P5fGCWhACNd54AwY-EyQQ", settings=CZECH_ONLY)
    assert tiles(state) == []


AUTOPLAY = {**SETTINGS, "profile1.autoplay": True}


def test_autoplay_videos_start_a_queue_of_the_rest_of_the_list(kodi):
    state = kodi("?action=category&p=1&c=kgQCCAM%253D", settings=AUTOPLAY)
    videos = [(url, item) for url, item, is_folder in state["items"] if not is_folder]
    first_url, first_item = videos[0]
    assert "IsPlayable" not in first_item.props  # run like RunPlugin
    ids = query(first_url)["v"].split(",")
    assert query(first_url)["action"] == "play"
    assert len(ids) == len(videos)
    last = query(videos[-1][0])["v"].split(",")
    assert last == [ids[-1]]
    second = query(videos[1][0])["v"].split(",")
    assert second == ids[1:]


def test_play_queues_videos_through_the_youtube_addon(kodi):
    state = kodi("?action=play&p=1&v=yYMD5_YB2S8,Sc586YYDasg,bad!id", settings=AUTOPLAY)
    urls = [url for url, _ in state["playlist"]]
    assert urls == [
        "plugin://plugin.video.youtube/play/?video_id=yYMD5_YB2S8",
        "plugin://plugin.video.youtube/play/?video_id=Sc586YYDasg",
    ]
    assert all(item.props["IsPlayable"] == "true" for _, item in state["playlist"])
    assert "played" in state and state["ended"] is None


def test_autoplay_off_keeps_direct_playback(kodi):
    state = kodi("?action=category&p=1&c=kgQCCAM%253D")
    url, item, _ = next(i for i in state["items"] if not i[2])
    assert url.startswith("plugin://plugin.video.youtube/play/")
    assert item.props["IsPlayable"] == "true"


def test_queue_shows_titles_of_listed_videos(kodi):
    listing = kodi("?action=category&p=1&c=kgQCCAM%253D", settings=AUTOPLAY)
    first_url, first_item, _ = next(i for i in listing["items"] if not i[2])
    state = kodi("?" + first_url.split("?", 1)[1], settings=AUTOPLAY)
    queued = [item for _, item in state["playlist"]]
    assert queued[0].label == first_item.label != ""
    assert queued[0].tag.data["title"] == first_item.label
    assert queued[0].tag.data["duration"] > 0
    assert all(item.label for item in queued)


def test_queue_of_unknown_videos_still_plays(kodi):
    state = kodi("?action=play&p=1&v=AAAAAAAAAAA", settings=AUTOPLAY)
    assert [url[-11:] for url, _ in state["playlist"]] == ["AAAAAAAAAAA"]
