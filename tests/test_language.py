import itertools
import json

import pytest

from littlescreen import language as lang
from littlescreen.catalog import Channel, Video
from littlescreen.packs import PACKS

CS, SK, OTHER = "cs", "sk", lang.OTHER

# Real titles from the CZ catalogue (2026-11-18): (title, channel, expected).
CASES = [
    ("Míša Růžičková - Paci paci - Písničky pro děti", "MÍŠA Růžičková", CS),
    (
        "Statečná autíčka | Kreslené pro Děti | Animované pro Děti",
        "Statečná autíčka (Český)",
        CS,
    ),
    ("Máša a Medvěd NOVÁ EPIZODA Princezna a zvíře Kolekce epizod", "Máša a Medvěd", CS),
    ("Večírek hraček | Bing: Celé epizody | Bing Český", "Bing Český - Oficiální Kanál", CS),
    (
        "Řecké písně pro děti - Den pernas kyra Maria ΔΕΝ ΠΕΡΝΑΣ ΚΥΡΑ ΜΑΡΙΑ - Dinolingo",
        "Dinolingo - Language learning for kids",
        CS,
    ),
    (
        "Keď si šťastný | Slovenské detské pesničky | Keď si šťastný",
        "Slovenské detské pesničky",
        SK,
    ),
    ("SPIEVANKOVO - TO NAJLEPŠIE ZA 18 ROKOV", "Kaufland Detský festival", SK),
    ("Päť cukríkov | Čarovná škôlka 1 | Detské pesničky", "BimBamKuku", SK),
    ("Miro Jaroš - ZLATÍČKO (Oficiálny videoklip)", "Galgan Music", SK),
    (
        "Zlí siví tvorovia! | Šmolkovia po slovensky | Rozprávky pre deti",
        "Šmolkovia • Slovenčina",
        SK,
    ),
    (
        "My sme smelí vojaci | Slovenské detské pesničky | czech kids songs",
        "Slovenské detské pesničky",
        SK,
    ),
    ("Ako si vyrobiť antistresovú loptičku | DIY", "Urob si sám – DIY Slovak", SK),
    (
        "Marshall ucieka przed wulkanem! - Tlapková patrola PAW Patrol - pohádky pro děti",
        "Psi Patrol Polski - Kanał Oficjalny",
        OTHER,
    ),
    ("30 minut Smrkcev • Zostavovanie potravín • Smrkci", "Smrkci • Slovenščina", OTHER),
    ("Dwayne Johnson - You're Welcome (from Moana/Official Video)", "DisneyMusicVEVO", OTHER),
    (
        "Boom Buddies Oopsie Doopsie שיר ריקוד + סרטונים מצוירים נוספים לתינוקות",
        "Kids Tv Israel - תכניוןת לילדים",
        OTHER,
    ),
    ("Тайна третьей планеты", "Союзмультфильм", OTHER),
    ("LOLLIPOPZ - První Láska (music video)", "Lollipopz", None),
    ("Bambulín a Berunka 14-26", "KEDD", None),
]


@pytest.mark.parametrize(("title", "channel", "expected"), CASES)
def test_czech_catalogue(title, channel, expected):
    assert lang.decide(lang.item_score(title, channel), "cs") == expected


@pytest.mark.parametrize(("title", "channel", "expected"), CASES)
def test_slovak_catalogue_sees_the_same_languages(title, channel, expected):
    assert lang.decide(lang.item_score(title, channel), "sk") == expected


# Real titles from other catalogues (2026-11-19), with the catalogue language (target).
# Without a pack only scripts and language names count.
SCRIPT_CASES = [
    # DE: Latin titles are German unless a name says otherwise.
    (
        "de",
        "Rubble Kommt Zur Polizei | PAW Patrol Auf Deutsch | Cartoons für Kinder",
        "PAW Patrol Deutschland",
        "de",
    ),
    ("de", "Moritz kauft sich alleine ein Eis | Der Elefant | WDR", "Der Elefant", "de"),
    ("de", "Schulnoten: Warum es früher keine 6 gab | 5½ Fakten", "logo!", "de"),
    ("de", "Śpiewaj z nami - Dżungla - Śpiewające Brzdące", "Śpiewające Brzdące", "de"),
    ("de", "44 Cats | Na tropie Kociego Ducha i wiele innych", "44 Cats - Polskie", OTHER),
    ("de", "Маша и Медведь - Восточные Сказки Машины песенки (Серия 11)", "Маша и Медведь", OTHER),
    ("de", "トムとジェリー | クラシック漫画 105 | WB Kids", "WB Kids International", None),
    (
        "de",
        "ちびまる子ちゃん初代エンディング「おどるポンポコリン」",
        "【公式】ちびまる子ちゃんねる",
        OTHER,
    ),
    # PL
    (
        "pl",
        "Mikołaju! Świąteczna Piosenka z Pokazywaniem || MeloMelo || Piosenki dla Dzieci",
        "MeloMelo",
        "pl",
    ),
    (
        "pl",
        "Co MIAU kot? | Kitness - zabawa ruchowa (рухлива гра), ćwiczenia dla dzieci "
        "(вправи для дітей)",
        "Akademia Krokieta i Lamy",
        None,  # Polish with Ukrainian in brackets: unclear, so it stays
    ),
    (
        "pl",
        "Winx Club: The Magic Is Back | Step into the Dark Trix Style Dance Mix!",
        "Klub Winx Polska",
        "pl",
    ),
    ("pl", "Peppa Wutz VERKLEIDET sich für die STEINZEIT!", "Peppa Pig Deutsch", OTHER),
    # RU
    (
        "ru",
        "Маша и Медведь НОВАЯ СЕРИЯ 2024 Бум-бум-барашек (серия 129) Masha and the Bear",
        "Маша и Медведь",
        "ru",
    ),
    ("ru", "Чуддики | Что со мной, Док? | Смешные мультики для детей", "ЧУДДИКИ На Русском", "ru"),
    ("ru", "Ladybugland Minuscule | 25' Compilation", "Minuscule", OTHER),
    (
        "ru",
        "Brain Break for kids/ Body percussion/Play-along/Hand clapping games",
        "Елена MUSICWAY",
        None,
    ),
    (
        "ru",
        "Турбозаври за 145 хвилин! Весь перший сезон українською",
        "Турбозаври — мультфільми українською",
        OTHER,
    ),
    # JA
    (
        "ja",
        "ブルーイと旅する | フルエピソード | ブルーイ - 日本公式チャンネル - Bluey",
        "ブルーイ - 日本公式チャンネル - Bluey",
        "ja",
    ),
    ("ja", "『トイ・ストーリー５』無料プレビュー", "ディズニー公式", "ja"),
    ("ja", "【ボンボン学園】女子だけでリンボーダンス対決やってみた！", "ボンボンTV", "ja"),
    ("ja", "The Mystery Door Talking Tom Shorts (S3 Episode 47)", "Talking Tom", OTHER),
    ("ja", "Кошки и их звуки для детей", "Котейка ТВ Животные", OTHER),
    # EN: Hindi titles mix Latin and Devanagari, the language name decides.
    (
        "en",
        "Peppa Pig in Hindi - The Tree House - हिंदी Kahaniya - Hindi Cartoons for Kids",
        "पेप्पा पिग का आधिकारिक हिंदी चैनल",
        OTHER,
    ),
    ("en", "Planets in the Solar System for Kids", "Learn Bright", "en"),
    (
        "en",
        "হাট্টিমাটিম টিম - Hattimatim Tim and more | Bengali Rhymes Collection | Infobells",
        "Infobells Bangla",
        OTHER,
    ),
    # A language named in English is often a lesson in English.
    (
        "en",
        "Simple Swahili Greetings (Hello Song + My Name Is) | Super Sema - Educational Kids Songs",
        "Super Sema",
        "en",
    ),
    # Czech markers mean nothing outside the Czech and Slovak catalogues.
    ("en", "Pro Skater Tricks", "Skate Kids", "en"),
    ("de", "Písničky pro děti", "Kids", "de"),
]


@pytest.mark.parametrize(("target", "title", "channel", "expected"), SCRIPT_CASES)
def test_other_catalogues_by_script_and_name(target, title, channel, expected):
    assert lang.decide(lang.item_score(title, channel), target) == expected


def test_word_lists_do_not_overlap():
    for a, b in itertools.combinations(PACKS, 2):
        assert not a.words & b.words, (a.code, b.code)
        assert not a.letters & b.letters, (a.code, b.code)
    names = set().union(*lang.NAMES.values())
    for pack in PACKS:
        assert not pack.words & names, pack.code
    assert sum(len(words) for words in lang.NAMES.values()) == len(names)


@pytest.mark.parametrize(
    ("hl", "code"),
    [("cs", "cs"), ("CS", "cs"), ("pt-BR", "pt"), ("zh-Hant", "zh"), ("iw", "he"), ("en_GB", "en")],
)
def test_target_language(hl, code):
    assert lang.target_language(hl) == code


def test_score_labels_do_not_depend_on_the_catalogue():
    assert lang.score("Písničky pro děti po slovensky") == {
        "cs": 3,
        "name:sk": 6,  # the word and the phrase
        "script:LATIN": 1,
    }
    assert lang.score("ブルーイ 日本 Bluey ½") == {"script:CJK+KANA+LATIN": 1}


def test_channel_memory_decides_titles_without_markers(tmp_path):
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    items = [
        Video("a", "Smejko a Tanculienka - Pozvánka na nové predstavenie", "Smejko", "UCs"),
        Video("b", "Smejko a Tanculienka - Benny", "Smejko", "UCs"),
        Video("c", "Čiperkové - Kola autobusu, Malý pavouček, Pejsek Bingo", "Čiperkové", "UCc"),
        Channel("UCc", "Čiperkové"),
        Video("d", "Zima", "wavdealer", "UCw"),
    ]
    result = lang.classify(items, memory, "cs")
    assert [result[id(i)] for i in items] == [SK, SK, CS, CS, None]


def test_memory_persists_and_stays_small(tmp_path):
    path = tmp_path / "c.json"
    memory = lang.ChannelMemory(str(path))
    for _ in range(40):
        memory.learn("UCx", {SK: 3})
    memory.save()
    data = json.loads(path.read_text())["counts"]
    assert 0 < data["UCx"][SK] <= 50
    assert lang.ChannelMemory(str(path)).get("UCx") == data["UCx"]


def test_memory_trims_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(lang, "CACHE_LIMIT", 2)
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    for cid in ("a", "b", "c"):
        memory.learn(cid, {CS: 1})
    assert list(memory.data) == ["b", "c"]


def test_broken_memory_file_is_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert lang.ChannelMemory(str(path)).data == {}


def test_keep_only_the_catalogue_language_and_unclear():
    mode = lang.CATALOGUE_LANGUAGE
    assert {x for x in (CS, SK, OTHER, None) if lang.keep(x, mode, "cs")} == {CS, None}
    assert all(lang.keep(x, lang.ANY_LANGUAGE, "cs") for x in (CS, SK, OTHER, None))


def test_filter_mode_reads_earlier_values_as_catalogue_language():
    assert lang.filter_mode(0) == lang.ANY_LANGUAGE
    for setting in (1, 2, 3):
        assert lang.filter_mode(setting) == lang.CATALOGUE_LANGUAGE


def test_unclear_channels_skips_decided_and_probed(tmp_path):
    memory = lang.ChannelMemory(str(tmp_path / "c.json"))
    items = [
        Video("a", "Zima", "x", "UC1"),
        Video("b", "Zima 2", "x", "UC1"),
        Video("c", "Písničky pro děti", "y", "UC2"),
        Video("d", "Benny", "z", "UC3"),
        Video("e", "Hu", "w", ""),
    ]
    result = lang.classify(items, memory, "cs")
    assert lang.unclear_channels(items, result, memory, 5) == ["UC1", "UC3"]
    memory.mark_probed("UC1")
    assert lang.unclear_channels(items, result, memory, 5) == ["UC3"]
    assert lang.unclear_channels(items, result, memory, 0) == []


def test_memory_file_keeps_probed_and_reads_old_format(tmp_path):
    path = tmp_path / "c.json"
    memory = lang.ChannelMemory(str(path))
    memory.learn("UCa", {SK: 2})
    memory.mark_probed("UCa")
    memory.save()
    again = lang.ChannelMemory(str(path))
    assert again.get("UCa")[SK] == 2 and again.was_probed("UCa")
    path.write_text(json.dumps({"UCb": {"cs": 1, "sk": 0, "other": 0}}))
    old = lang.ChannelMemory(str(path))
    assert old.get("UCb")["cs"] == 1 and not old.was_probed("UCb")
    # Counts from 0.4 are markers: they speak in the Czech catalogue only.
    assert lang.channel_language(old, "UCb", "cs") == CS
    assert lang.channel_language(old, "UCb", "de") is None


def test_probes_are_kept_per_age_group(tmp_path):
    path = str(tmp_path / "c.json")
    toddler = lang.ChannelMemory(path, "PRESCHOOL")
    toddler.mark_probed("UCa", has_videos=False)
    toddler.learn("UCa", {CS: 2})
    toddler.save()
    older = lang.ChannelMemory(path, "YOUNGER")
    assert older.has_videos("UCa") is None and not older.was_probed("UCa")
    assert older.get("UCa")[CS] == 2  # language evidence is shared
    assert lang.ChannelMemory(path, "PRESCHOOL").has_videos("UCa") is False
