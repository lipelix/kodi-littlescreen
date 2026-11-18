import json

import pytest

from littlescreen import language as lang
from littlescreen.catalog import Channel, Video

# Real titles from the CZ catalogue (2026-11-18): (title, channel, expected).
CASES = [
    ("Míša Růžičková - Paci paci - Písničky pro děti", "MÍŠA Růžičková", lang.CS),
    (
        "Statečná autíčka | Kreslené pro Děti | Animované pro Děti",
        "Statečná autíčka (Český)",
        lang.CS,
    ),
    ("Máša a Medvěd NOVÁ EPIZODA Princezna a zvíře Kolekce epizod", "Máša a Medvěd", lang.CS),
    ("Večírek hraček | Bing: Celé epizody | Bing Český", "Bing Český - Oficiální Kanál", lang.CS),
    (
        "Keď si šťastný | Slovenské detské pesničky | Keď si šťastný",
        "Slovenské detské pesničky",
        lang.SK,
    ),
    ("SPIEVANKOVO - TO NAJLEPŠIE ZA 18 ROKOV", "Kaufland Detský festival", lang.SK),
    ("Päť cukríkov | Čarovná škôlka 1 | Detské pesničky", "BimBamKuku", lang.SK),
    ("Miro Jaroš - ZLATÍČKO (Oficiálny videoklip)", "Galgan Music", lang.SK),
    (
        "Zlí siví tvorovia! | Šmolkovia po slovensky | Rozprávky pre deti",
        "Šmolkovia • Slovenčina",
        lang.SK,
    ),
    (
        "My sme smelí vojaci | Slovenské detské pesničky | czech kids songs",
        "Slovenské detské pesničky",
        lang.SK,
    ),
    ("Ako si vyrobiť antistresovú loptičku | DIY", "Urob si sám – DIY Slovak", lang.SK),
    (
        "Marshall ucieka przed wulkanem! - Tlapková patrola PAW Patrol - pohádky pro děti",
        "Psi Patrol Polski - Kanał Oficjalny",
        lang.OTHER,
    ),
    ("30 minut Smrkcev • Zostavovanie potravín • Smrkci", "Smrkci • Slovenščina", lang.OTHER),
    ("Dwayne Johnson - You're Welcome (from Moana/Official Video)", "DisneyMusicVEVO", lang.OTHER),
    ("Boom Buddies שיר ריקוד + סרטונים מצוירים", "Kids Tv Israel", lang.OTHER),
    ("LOLLIPOPZ - První Láska (music video)", "Lollipopz", None),
    ("Bambulín a Berunka 14-26", "KEDD", None),
]


@pytest.mark.parametrize(("title", "channel", "expected"), CASES)
def test_item_language(title, channel, expected):
    assert lang.decide(lang.item_score(title, channel)) == expected


def test_word_lists_do_not_overlap():
    assert not lang._AMBIGUOUS


def test_channel_memory_decides_titles_without_markers(tmp_path):
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    items = [
        Video("a", "Smejko a Tanculienka - Pozvánka na nové predstavenie", "Smejko", "UCs"),
        Video("b", "Smejko a Tanculienka - Benny", "Smejko", "UCs"),
        Video("c", "Čiperkové - Kola autobusu, Malý pavouček, Pejsek Bingo", "Čiperkové", "UCc"),
        Channel("UCc", "Čiperkové"),
        Video("d", "Zima", "wavdealer", "UCw"),
    ]
    result = lang.classify(items, memory)
    assert [result[id(i)] for i in items] == [lang.SK, lang.SK, lang.CS, lang.CS, None]


def test_memory_persists_and_stays_small(tmp_path):
    path = tmp_path / "c.json"
    memory = lang.ChannelMemory(str(path))
    for _ in range(40):
        memory.learn("UCx", {lang.SK: 3})
    memory.save()
    data = json.loads(path.read_text())["counts"]
    assert 0 < data["UCx"][lang.SK] <= 50
    assert lang.ChannelMemory(str(path)).get("UCx") == data["UCx"]


def test_memory_trims_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(lang, "CACHE_LIMIT", 2)
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    for cid in ("a", "b", "c"):
        memory.learn(cid, {lang.CS: 1})
    assert list(memory.data) == ["b", "c"]


def test_broken_memory_file_is_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert lang.ChannelMemory(str(path)).data == {}


@pytest.mark.parametrize(
    ("mode", "kept"),
    [
        (lang.SHOW_ALL, {lang.CS, lang.SK, lang.OTHER, None}),
        (lang.HIDE_SLOVAK, {lang.CS, lang.OTHER, None}),
        (lang.CZECH_ONLY, {lang.CS, None}),
    ],
)
def test_keep(mode, kept):
    assert {x for x in (lang.CS, lang.SK, lang.OTHER, None) if lang.keep(x, mode)} == kept


def test_unclear_channels_skips_decided_and_probed(tmp_path):
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    items = [
        Video("a", "Zima", "x", "UC1"),
        Video("b", "Zima 2", "x", "UC1"),
        Video("c", "Písničky pro děti", "y", "UC2"),
        Video("d", "Benny", "z", "UC3"),
        Video("e", "Hu", "w", ""),
    ]
    result = lang.classify(items, memory)
    assert lang.unclear_channels(items, result, memory, 5) == ["UC1", "UC3"]
    memory.mark_probed("UC1")
    assert lang.unclear_channels(items, result, memory, 5) == ["UC3"]
    assert lang.unclear_channels(items, result, memory, 0) == []


def test_memory_file_keeps_probed_and_reads_old_format(tmp_path):
    path = tmp_path / "c.json"
    memory = lang.ChannelMemory(str(path))
    memory.learn("UCa", {lang.SK: 2})
    memory.mark_probed("UCa")
    memory.save()
    again = lang.ChannelMemory(str(path))
    assert again.get("UCa")[lang.SK] == 2 and again.was_probed("UCa")
    path.write_text(json.dumps({"UCb": {"cs": 1, "sk": 0, "other": 0}}))
    old = lang.ChannelMemory(str(path))
    assert old.get("UCb")["cs"] == 1 and not old.was_probed("UCb")


def test_probes_are_kept_per_age_group(tmp_path):
    path = str(tmp_path / "c.json")
    toddler = lang.ChannelMemory(path, "PRESCHOOL")
    toddler.mark_probed("UCa", has_videos=False)
    toddler.learn("UCa", {lang.CS: 2})
    toddler.save()
    older = lang.ChannelMemory(path, "YOUNGER")
    assert older.has_videos("UCa") is None and not older.was_probed("UCa")
    assert older.get("UCa")[lang.CS] == 2  # language evidence is shared
    assert lang.ChannelMemory(path, "PRESCHOOL").has_videos("UCa") is False
