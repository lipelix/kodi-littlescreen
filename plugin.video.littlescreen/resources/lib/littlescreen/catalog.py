"""Turn YouTube Kids InnerTube responses into plain items.

The parser walks the whole response for the renderers it knows instead of
following exact paths, so small layout changes on YouTube's side do not break it.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Video:
    video_id: str
    title: str
    channel: str = ""
    channel_id: str = ""
    duration: int = 0  # seconds

    @property
    def thumbnail(self):
        return f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg"


@dataclass
class Channel:
    channel_id: str
    title: str
    thumbnail: str = ""
    banner: str = ""


@dataclass
class Category:
    title: str
    params: str
    asset_key: str = ""
    color: str = ""
    selected: bool = False


@dataclass
class Page:
    items: list[object] = field(default_factory=list)
    continuation: Optional[str] = None
    title: str = ""


# Emoji and pictographs: Kodi's fonts lack them, and a label that starts with one
# is drawn empty in Estuary.
_PICTOGRAPHS = re.compile(
    "[\U0001f000-\U0001faff\u2190-\u21ff\u2300-\u23ff\u2600-\u27bf\u2b00-\u2bff"
    "\ufe0e\ufe0f\u200d\u20e3]"
)
_SPACES = re.compile(r"\s{2,}")


def clean_label(value):
    return _SPACES.sub(" ", _PICTOGRAPHS.sub("", value)).strip()


def text(node):
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    return "".join(run.get("text", "") for run in node.get("runs", []))


def parse_duration(value):
    """'1:05:01' -> 3901. Unknown formats give 0."""
    seconds = 0
    for part in value.split(":"):
        if not part.isdigit():
            return 0
        seconds = seconds * 60 + int(part)
    return seconds


def _largest(thumbnails):
    if not thumbnails:
        return ""
    url = max(thumbnails, key=lambda t: t.get("width", 0)).get("url", "")
    return "https:" + url if url.startswith("//") else url


def _video(renderer):
    video_id = renderer.get("videoId")
    if not video_id:
        return None
    byline = renderer.get("shortBylineText") or renderer.get("longBylineText") or {}
    channel_id = renderer.get("kidsVideoOwnerExtension", {}).get("externalChannelId", "")
    if not channel_id:
        for run in byline.get("runs", []):
            channel_id = (
                run.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
            )
            if channel_id:
                break
    return Video(
        video_id=video_id,
        title=clean_label(text(renderer.get("title"))),
        channel=clean_label(text(byline)),
        channel_id=channel_id,
        duration=parse_duration(text(renderer.get("lengthText"))),
    )


def _channel(renderer):
    channel_id = renderer.get("channelId")
    if not channel_id:
        return None
    return Channel(
        channel_id=channel_id,
        title=clean_label(text(renderer.get("title")) or text(renderer.get("displayName"))),
        thumbnail=_largest(renderer.get("thumbnail", {}).get("thumbnails")),
        banner=_largest(renderer.get("tvBanner", {}).get("thumbnails")),
    )


def _continuation_token(node):
    for cont in node.get("continuations", []):
        token = cont.get("nextContinuationData", {}).get("continuation")
        if token:
            return token
    command = node.get("continuationItemRenderer", {}).get("continuationEndpoint", {})
    return command.get("continuationCommand", {}).get("token")


def parse_items(node):
    """Collect videos and channels in page order, without duplicates."""
    page = Page()
    seen = set()

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "compactVideoRenderer":
                    item = _video(value)
                elif key == "compactChannelRenderer":
                    item = _channel(value)
                else:
                    if isinstance(value, (dict, list)):
                        if isinstance(value, dict) and page.continuation is None:
                            page.continuation = _continuation_token(value)
                        walk(value)
                    continue
                if item is not None:
                    key_id = getattr(item, "video_id", None) or item.channel_id
                    if key_id not in seen:
                        seen.add(key_id)
                        page.items.append(item)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    if isinstance(node, dict) and page.continuation is None:
        page.continuation = _continuation_token(node)
    walk(node)
    return page


def parse_home(response):
    """Return (categories, page of the selected category)."""
    anchors = response.get("contents", {}).get("kidsHomeScreenRenderer", {}).get("anchors", [])
    categories = []
    page = Page()
    for anchor in anchors:
        section = anchor.get("anchoredSectionRenderer")
        if not section:
            continue
        browse = section.get("navigationEndpoint", {}).get("browseEndpoint", {})
        assets = section.get("categoryAssets", {})
        selected = "content" in section
        categories.append(
            Category(
                title=section.get("title", ""),
                params=browse.get("params", ""),
                asset_key=assets.get("assetKey", ""),
                color=assets.get("backgroundColor", ""),
                selected=selected,
            )
        )
        if selected:
            page = parse_items(section["content"])
            page.title = section.get("title", "")
    return categories, page


def parse_channel(response):
    page = parse_items(response.get("contents", {}))
    header = response.get("header", {})
    for renderer in header.values():
        if isinstance(renderer, dict) and renderer.get("title"):
            title = renderer["title"]
            page.title = title if isinstance(title, str) else text(title)
            break
    return page


def parse_continuation(response):
    return parse_items(
        response.get("continuationContents") or response.get("onResponseReceivedActions", {})
    )


def parse_search(response):
    return parse_items(response.get("contents", {}))
