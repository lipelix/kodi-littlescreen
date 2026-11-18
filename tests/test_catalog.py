from littlescreen import catalog


def test_home_lists_categories_with_selected_first(fixture):
    categories, page = catalog.parse_home(fixture("home_preschool.json"))
    assert [c.asset_key for c in categories] == ["shows", "music", "learning", "explore"]
    assert categories[0].selected and not categories[1].selected
    assert categories[1].params == "kgQCCAM%3D"
    assert categories[2].color == "#CC26A1"
    assert page.title == "Pořady"
    assert len(page.items) > 20


def test_tween_home_has_gaming(fixture):
    categories, _ = catalog.parse_home(fixture("home_tween.json"))
    assert "gaming" in [c.asset_key for c in categories]


def test_category_page_selects_requested_anchor(fixture):
    categories, page = catalog.parse_home(fixture("home_music.json"))
    assert [c.title for c in categories] == ["Hudba"]
    assert page.title == "Hudba"
    assert page.items


def test_video_fields(fixture):
    _, page = catalog.parse_home(fixture("home_preschool.json"))
    video = page.items[0]
    assert isinstance(video, catalog.Video)
    assert video.video_id == "yYMD5_YB2S8"
    assert video.title == "Bambulín a Berunka 14-26"
    assert video.channel == "KEDD"
    assert video.channel_id == "UC6Ap2GH9CQAO_bVjt9W4VhA"
    assert video.duration == 3901
    assert video.thumbnail == "https://i.ytimg.com/vi/yYMD5_YB2S8/hqdefault.jpg"


def test_items_are_unique_and_include_channels(fixture):
    _, page = catalog.parse_home(fixture("home_preschool.json"))
    ids = [getattr(i, "video_id", None) or i.channel_id for i in page.items]
    assert len(ids) == len(set(ids))
    channels = [i for i in page.items if isinstance(i, catalog.Channel)]
    assert channels
    assert channels[0].banner.startswith("https://")
    assert channels[0].thumbnail.startswith("https://")


def test_channel_page_has_title_and_continuation(fixture):
    page = catalog.parse_channel(fixture("channel.json"))
    assert page.title == "Statečná autíčka (Český)"
    assert len(page.items) == 40
    assert page.continuation


def test_continuation_page(fixture):
    page = catalog.parse_continuation(fixture("channel_continuation.json"))
    assert len(page.items) == 100
    assert page.continuation


def test_search_results(fixture):
    page = catalog.parse_search(fixture("search.json"))
    assert len(page.items) == 20
    assert all(isinstance(i, catalog.Video) for i in page.items)
    assert page.continuation


def test_parse_duration():
    assert catalog.parse_duration("4:05") == 245
    assert catalog.parse_duration("1:05:01") == 3901
    assert catalog.parse_duration("") == 0
    assert catalog.parse_duration("LIVE") == 0


def test_text_handles_simple_and_runs():
    assert catalog.text({"simpleText": "a"}) == "a"
    assert catalog.text({"runs": [{"text": "a"}, {"text": "b"}]}) == "ab"
    assert catalog.text(None) == ""


def test_clean_label_drops_emoji():
    assert catalog.clean_label("🐭➕ Mickeyho nový pomocníček") == "Mickeyho nový pomocníček"
    assert catalog.clean_label("Zábavné ✨ hrátky • Bluey ❤️") == "Zábavné hrátky • Bluey"
    assert catalog.clean_label("Pták Pohromák | EP14") == "Pták Pohromák | EP14"
