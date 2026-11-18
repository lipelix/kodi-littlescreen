"""Client for the unofficial InnerTube API behind www.youtubekids.com (client WEB_KIDS).

Signed out, the API serves the YouTube Kids catalogue for one age group, chosen
with ``kidsAppInfo.contentSettings.corpusPreference``. The client version is
read from the youtubekids.com page and cached, since YouTube rejects old ones.
"""

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen

BASE_URL = "https://www.youtubekids.com"
CLIENT_NAME = "WEB_KIDS"
CLIENT_NAME_ID = "76"
HOME_BROWSE_ID = "FEkids_home"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
CONFIG_MAX_AGE = 24 * 60 * 60
TIMEOUT = 15

# YouTube Kids age groups: 4 and under, 5-8, 9-12.
AGE_GROUPS = ("PRESCHOOL", "YOUNGER", "TWEEN")

_VERSION_RE = re.compile(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"')
_STABLE_RE = re.compile(r"\d+\.\d{8}\.\d+\.\d+")


class InnerTubeError(Exception):
    """The API could not be reached or answered with an error."""


def parse_client_version(html):
    match = _VERSION_RE.search(html)
    if not match:
        raise InnerTubeError("INNERTUBE_CLIENT_VERSION not found on youtubekids.com")
    # Some page loads carry an experiment build, e.g.
    # "2.20261117.10.00-canary_experiment_2.20261117.00.00": use the stable version in it.
    versions = _STABLE_RE.findall(match.group(1))
    if not versions:
        raise InnerTubeError(f"Unexpected client version: {match.group(1)!r}")
    return versions[-1]


def _http(url, data=None, headers=None):
    request = Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8")
    except HTTPError as err:
        raise InnerTubeError(f"HTTP {err.code} from {url}") from err
    except URLError as err:
        raise InnerTubeError(f"Cannot reach {url}: {err.reason}") from err


class KidsClient:
    def __init__(self, age_group, hl, gl, cache_file, http=_http, clock=time.time):
        if age_group not in AGE_GROUPS:
            raise ValueError(f"Unknown age group: {age_group}")
        self.age_group = age_group
        self.hl = hl
        self.gl = gl
        self.cache_file = cache_file
        self._http = http
        self._clock = clock
        self._version = None

    # -- client version ---------------------------------------------------

    def client_version(self):
        if self._version:
            return self._version
        cached = self._read_cache()
        if cached and self._clock() - cached.get("fetched", 0) < CONFIG_MAX_AGE:
            self._version = cached["version"]
            return self._version
        try:
            return self.refresh_client_version()
        except InnerTubeError:
            if not cached or not cached.get("version"):
                raise
            # An old version usually still works; better than no catalogue at all.
            self._version = cached["version"]
            return self._version

    def refresh_client_version(self):
        html = self._http(f"{BASE_URL}/?hl={self.hl}&gl={self.gl}")
        self._version = parse_client_version(html)
        self._write_cache({"version": self._version, "fetched": self._clock()})
        return self._version

    def _read_cache(self):
        try:
            with open(self.cache_file, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _write_cache(self, data):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except OSError:
            pass  # caching is an optimisation only

    # -- requests ---------------------------------------------------------

    def context(self, version):
        return {
            "client": {
                "clientName": CLIENT_NAME,
                "clientVersion": version,
                "hl": self.hl,
                "gl": self.gl,
                "kidsAppInfo": {
                    "contentSettings": {
                        "corpusPreference": f"KIDS_CORPUS_PREFERENCE_{self.age_group}",
                        "kidsNoSearchMode": "YT_KIDS_NO_SEARCH_MODE_OFF",
                    }
                },
            }
        }

    def post(self, endpoint, payload, _retried=False):
        version = self.client_version()
        body = json.dumps({"context": self.context(version), **payload}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Origin": BASE_URL,
            "X-YouTube-Client-Name": CLIENT_NAME_ID,
            "X-YouTube-Client-Version": version,
        }
        url = f"{BASE_URL}/youtubei/v1/{endpoint}?prettyPrint=false"
        try:
            data = json.loads(self._http(url, data=body, headers=headers))
        except InnerTubeError:
            if _retried:
                raise
            # A stale client version is the usual cause; fetch a fresh one once.
            self.refresh_client_version()
            return self.post(endpoint, payload, _retried=True)
        except ValueError as err:
            raise InnerTubeError(f"Invalid JSON from {endpoint}") from err
        if "error" in data:
            raise InnerTubeError(data["error"].get("message", "API error"))
        return data

    def home(self, category_params=None):
        payload = {"browseId": HOME_BROWSE_ID}
        if category_params:
            payload["params"] = unquote(category_params)
        return self.post("browse", payload)

    def channel(self, channel_id):
        return self.post("browse", {"browseId": channel_id})

    def continuation(self, token):
        return self.post("browse", {"continuation": token})

    def search(self, query):
        return self.post("search", {"query": query})

    def search_continuation(self, token):
        return self.post("search", {"continuation": token})
