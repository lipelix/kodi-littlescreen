"""Hits the real YouTube Kids API. Run with LIVE=1."""

import os

import pytest

from littlescreen import catalog
from littlescreen.innertube import AGE_GROUPS, KidsClient

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("LIVE"), reason="set LIVE=1 to hit the real API"),
]


@pytest.mark.parametrize("age", AGE_GROUPS)
def test_every_age_group_browses(tmp_path, age):
    client = KidsClient(age, "cs", "CZ", str(tmp_path / "c.json"))
    categories, page = catalog.parse_home(client.home())
    assert len(categories) >= 3
    assert len(page.items) > 10
    other = next(c for c in categories if not c.selected)
    _, other_page = catalog.parse_home(client.home(other.params))
    assert other_page.title == other.title and other_page.items


def test_channel_paging_and_search(tmp_path):
    client = KidsClient("YOUNGER", "cs", "CZ", str(tmp_path / "c.json"))
    _, page = catalog.parse_home(client.home())
    video = next(i for i in page.items if isinstance(i, catalog.Video) and i.channel_id)
    channel = catalog.parse_channel(client.channel(video.channel_id))
    assert channel.items
    if channel.continuation:
        assert catalog.parse_continuation(client.continuation(channel.continuation)).items
    results = catalog.parse_search(client.search("krtek"))
    assert results.items
    if results.continuation:
        assert catalog.parse_continuation(client.search_continuation(results.continuation)).items
