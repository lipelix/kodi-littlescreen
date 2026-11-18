import json

import pytest

from ytkids.innertube import InnerTubeError, KidsClient, parse_client_version

HTML = '<script>ytcfg.set({"INNERTUBE_CLIENT_VERSION":"2.20261117.00.00","X":1})</script>'


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, data=None, headers=None):
        self.calls.append((url, json.loads(data) if data else None, headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make(tmp_path, responses, now=1000.0, age="PRESCHOOL"):
    http = FakeHttp(responses)
    client = KidsClient(age, "cs", "CZ", str(tmp_path / "c.json"), http=http, clock=lambda: now)
    return client, http


def test_parse_client_version():
    assert parse_client_version(HTML) == "2.20261117.00.00"
    with pytest.raises(InnerTubeError):
        parse_client_version("<html></html>")


def test_request_carries_age_group_and_version(tmp_path):
    client, http = make(tmp_path, [HTML, '{"contents":{}}'], age="YOUNGER")
    client.home("kgQCCAM%3D")
    url, body, headers = http.calls[1]
    assert url.startswith("https://www.youtubekids.com/youtubei/v1/browse")
    assert body["browseId"] == "FEkids_home"
    assert body["params"] == "kgQCCAM="
    settings = body["context"]["client"]["kidsAppInfo"]["contentSettings"]
    assert settings["corpusPreference"] == "KIDS_CORPUS_PREFERENCE_YOUNGER"
    assert body["context"]["client"]["clientVersion"] == "2.20261117.00.00"
    assert headers["X-YouTube-Client-Name"] == "76"


def test_version_is_cached_for_a_day(tmp_path):
    client, http = make(tmp_path, [HTML, "{}"])
    client.search("krtek")
    again, http2 = make(tmp_path, ["{}"], now=1000.0 + 3600)
    again.search("krtek")
    assert len(http2.calls) == 1  # no page fetch
    stale, http3 = make(tmp_path, [HTML, "{}"], now=1000.0 + 2 * 86400)
    stale.search("krtek")
    assert "youtubei" not in http3.calls[0][0]


def test_failed_request_refreshes_version_once(tmp_path):
    client, http = make(tmp_path, [HTML, InnerTubeError("HTTP 400"), HTML, '{"ok":1}'])
    assert client.channel("UCx") == {"ok": 1}
    with pytest.raises(InnerTubeError):
        bad, _ = make(
            tmp_path, [InnerTubeError("HTTP 400"), HTML, InnerTubeError("HTTP 400")], now=1000.0
        )
        bad.channel("UCx")


def test_api_error_raises(tmp_path):
    client, _ = make(tmp_path, [HTML, '{"error":{"code":400,"message":"Invalid value"}}'])
    with pytest.raises(InnerTubeError, match="Invalid value"):
        client.home()


def test_unknown_age_group(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path, [], age="OLDER")


def test_parse_client_version_of_an_experiment_build():
    html = '"INNERTUBE_CLIENT_VERSION":"2.20261117.10.00-canary_experiment_2.20261117.00.00"'
    assert parse_client_version(html) == "2.20261117.00.00"
    with pytest.raises(InnerTubeError):
        parse_client_version('"INNERTUBE_CLIENT_VERSION":"garbage"')


def test_stale_version_is_used_when_the_page_fails(tmp_path):
    client, _ = make(tmp_path, [HTML, "{}"])
    client.search("krtek")
    later, http = make(tmp_path, [InnerTubeError("HTTP 503"), "{}"], now=1000.0 + 2 * 86400)
    later.search("krtek")
    assert http.calls[1][2]["X-YouTube-Client-Version"] == "2.20261117.00.00"
