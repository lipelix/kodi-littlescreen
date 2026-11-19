from littlescreen import language, region

LANGINFO = """<?xml version="1.0" encoding="UTF-8"?>
<language>
  <regions>
    <region name="USA (12h)" locale="US"><dateshort>MM/DD/YYYY</dateshort></region>
    <region name="UK (24h)" locale="GB"/>
    <region name="Central Europe" locale="de"/>
    <region name="Nowhere" locale="EUR"/>
    <region name="Old"/>
  </regions>
</language>"""


def test_region_from_langinfo():
    assert region.region_from_langinfo(LANGINFO, "UK (24h)") == "GB"
    assert region.region_from_langinfo(LANGINFO, "Central Europe") == "DE"


def test_region_from_langinfo_without_a_country_code():
    assert region.region_from_langinfo(LANGINFO, "Nowhere") is None
    assert region.region_from_langinfo(LANGINFO, "Old") is None
    assert region.region_from_langinfo(LANGINFO, "Mars") is None
    assert region.region_from_langinfo(LANGINFO, None) is None
    assert region.region_from_langinfo(None, "UK (24h)") is None
    assert region.region_from_langinfo("<not xml", "UK (24h)") is None


def test_language_addon_parts():
    assert region.language_addon_parts("resource.language.de_de") == ("de", "DE")
    assert region.language_addon_parts("resource.language.pt_br") == ("pt", "BR")
    assert region.language_addon_parts("resource.language.sr_rs@latin") == ("sr", "RS")
    assert region.language_addon_parts("resource.language.ast_es") == ("ast", "ES")
    assert region.language_addon_parts("resource.language.eo") == ("eo", None)
    assert region.language_addon_parts("skin.estuary") == (None, None)
    assert region.language_addon_parts(None) == (None, None)


def test_kodi_language():
    assert region.kodi_language("de", "resource.language.de_de") == "de"
    assert region.kodi_language("cs", "resource.language.cs_cz") == "cs"
    assert region.kodi_language("pt", "resource.language.pt_br") == "pt"
    assert region.kodi_language("pt", "resource.language.pt_pt") == "pt-PT"
    assert region.kodi_language("zh", "resource.language.zh_tw") == "zh-TW"
    assert region.kodi_language("", "resource.language.nb_no") == "nb"


def test_kodi_language_youtube_does_not_offer():
    assert region.kodi_language("", "resource.language.ast_es") is None
    assert region.kodi_language("cy", "resource.language.cy_gb") is None
    assert region.kodi_language("eo", "resource.language.eo") is None
    assert region.kodi_language("", None) is None


def test_kodi_region_reads_the_language_addon():
    files = {"special://xbmc/addons/resource.language.en_gb/resources/langinfo.xml": LANGINFO}
    assert region.kodi_region("resource.language.en_gb", "USA (12h)", files.get) == "US"
    # Region not in the file (or no file): the country of the language add-on.
    assert region.kodi_region("resource.language.en_gb", "Mars", files.get) == "GB"
    assert region.kodi_region("resource.language.de_de", "Deutschland", files.get) == "DE"
    assert region.kodi_region("resource.language.eo", "Mondo", files.get) is None
    assert region.kodi_region(None, None, files.get) is None


def test_kodi_region_prefers_the_installed_language_addon():
    files = {
        "special://home/addons/resource.language.de_de/resources/langinfo.xml": (
            '<l><regions><region name="Schweiz" locale="CH"/></regions></l>'
        ),
        "special://xbmc/addons/resource.language.de_de/resources/langinfo.xml": LANGINFO,
    }
    assert region.kodi_region("resource.language.de_de", "Schweiz", files.get) == "CH"


def test_resolve_manual_settings_win():
    def kodi():
        raise AssertionError("Kodi is not asked when the setting is filled in")

    assert region.resolve("cs", "cz", kodi, kodi) == ("cs", "CZ")
    assert region.resolve(" sk ", " SK ", kodi, kodi) == ("sk", "SK")


def test_resolve_empty_settings_follow_kodi():
    assert region.resolve("", "", lambda: "de", lambda: "AT") == ("de", "AT")
    assert region.resolve("", "PL", lambda: "de", lambda: "AT") == ("de", "PL")


def test_resolve_falls_back_when_kodi_does_not_say():
    assert region.resolve("", "", lambda: None, lambda: None) == ("en", "US")


def test_filter_mode_automatic_follows_the_catalogue_language():
    assert language.filter_mode(language.AUTOMATIC, "cs") == language.CZECH_ONLY
    assert language.filter_mode(language.AUTOMATIC, "CS") == language.CZECH_ONLY
    assert language.filter_mode(language.AUTOMATIC, "de") == language.SHOW_ALL
    assert language.filter_mode(language.AUTOMATIC, "en-GB") == language.SHOW_ALL


def test_filter_mode_manual_choice_stays():
    for mode in (language.SHOW_ALL, language.HIDE_SLOVAK, language.CZECH_ONLY):
        assert language.filter_mode(mode, "de") == mode
