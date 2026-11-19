"""Kodi directory listings for Little Screen (the YouTube Kids catalogue)."""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from littlescreen import catalog, language, region
from littlescreen.innertube import AGE_GROUPS, InnerTubeError, KidsClient
from littlescreen.profiles import find_profile, load_profiles
from littlescreen.videocache import VideoCache

LOG_PREFIX = "[plugin.video.littlescreen]"
YOUTUBE_PLAY = "plugin://plugin.video.youtube/play/?video_id={}"
ESTUARY = "skin.estuary"
VIEW_WALL = 500
VIEW_WIDELIST = 55
VIEW_WAIT_STEPS = 30  # x 100 ms
MIN_ITEMS = 12  # top a filtered page up from the next pages until it has this many
MAX_EXTRA_PAGES = 3
PROBE_CHANNELS = 8  # channel pages read per listing to learn unclear channels' language
PROBE_TILES = 12  # channel pages read per category to check channel tiles
PROBE_WORKERS = 6
AUTOPLAY_QUEUE = 50  # videos queued after a pick when autoplay is on
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")

S_SEARCH = 30030
S_MORE = 30031
S_LOAD_FAILED = 30032
S_NO_PROFILE = 30033
S_NOTHING_FOUND = 30034
S_WHO = 30035
S_AGE_NAMES = (30050, 30051, 30052)  # by AGE_GROUPS


class Plugin:
    def __init__(self, argv):
        self.base_url = argv[0]
        self.handle = int(argv[1])
        self.params = dict(parse_qsl(argv[2].lstrip("?")))
        self.path = argv[0] + argv[2]
        self._clients = {}
        self.addon = xbmcaddon.Addon()
        self.media = os.path.join(
            xbmcvfs.translatePath(self.addon.getAddonInfo("path")), "resources", "media"
        )
        self.profiles = load_profiles(
            self.addon.getSettingBool,
            self.addon.getSettingInt,
            self.addon.getSettingString,
            age_label=lambda age: self.tr(S_AGE_NAMES[AGE_GROUPS.index(age)]),
        )
        self._locale = None

    # -- helpers ----------------------------------------------------------

    def tr(self, string_id):
        return self.addon.getLocalizedString(string_id)

    def url(self, **query):
        return f"{self.base_url}?{urlencode(query)}"

    def media_file(self, name):
        path = os.path.join(self.media, name)
        return path if os.path.exists(path) else os.path.join(self.media, "default.png")

    def data_file(self, name):
        data_dir = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        xbmcvfs.mkdirs(data_dir)
        return os.path.join(data_dir, name)

    def client(self, profile):
        if profile.slot not in self._clients:
            self._clients[profile.slot] = self.new_client(profile)
        return self._clients[profile.slot]

    def locale(self):
        """(hl, gl) of the catalogue: the add-on settings, or Kodi's language and region."""
        if self._locale is None:
            self._locale = region.resolve(
                self.addon.getSettingString("hl"),
                self.addon.getSettingString("gl"),
                kodi_hl=lambda: region.kodi_language(
                    xbmc.getLanguage(xbmc.ISO_639_1), kodi_setting("locale.language")
                ),
                kodi_gl=lambda: region.kodi_region(
                    kodi_setting("locale.language"), kodi_setting("locale.country"), read_text
                ),
            )
            xbmc.log(
                f"{LOG_PREFIX} catalogue hl={self._locale[0]} gl={self._locale[1]}", xbmc.LOGDEBUG
            )
        return self._locale

    def new_client(self, profile):
        hl, gl = self.locale()
        return KidsClient(
            age_group=profile.age_group, hl=hl, gl=gl, cache_file=self.data_file("client.json")
        )

    def folder(self, label, url, image, fanart=None, is_folder=True):
        item = xbmcgui.ListItem(label, offscreen=True)
        item.setArt(
            {
                "thumb": image,
                "icon": image,
                "poster": image,
                "fanart": fanart or os.path.join(self.media, "..", "fanart.jpg"),
            }
        )
        tag = item.getVideoInfoTag()
        tag.setTitle(label)
        xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=is_folder)

    def finish(self, profile, title, cache=True):
        xbmcplugin.setPluginCategory(self.handle, title)
        xbmcplugin.setContent(self.handle, "videos")
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(self.handle, cacheToDisc=cache)
        if xbmc.getSkinDir() == ESTUARY and self.wait_for_container():
            toddler = profile is None or profile.toddler
            xbmc.executebuiltin(f"Container.SetViewMode({VIEW_WALL if toddler else VIEW_WIDELIST})")

    def wait_for_container(self):
        """Wait until Kodi shows this listing; a view mode set earlier is lost."""
        for _ in range(VIEW_WAIT_STEPS):
            if same_listing(xbmc.getInfoLabel("Container.FolderPath"), self.path):
                return True
            xbmc.sleep(100)
        return False  # listed without the GUI, e.g. over JSON-RPC

    def fail(self, message):
        xbmc.log(f"{LOG_PREFIX} {message}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            self.addon.getAddonInfo("name"), self.tr(S_LOAD_FAILED), xbmcgui.NOTIFICATION_ERROR
        )
        xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    # -- routing ----------------------------------------------------------

    def run(self):
        action = self.params.get("action")
        if action is None:
            return self.start()
        profile = find_profile(self.profiles, int(self.params.get("p", "0")))
        if profile is None:
            # The profile was switched off since this listing was made.
            return self.start()
        handler = {
            "home": self.home,
            "category": self.category,
            "channel": self.channel,
            "more": self.more,
            "ask": self.ask,
            "play": self.play,
            "search": self.search,
        }.get(action)
        if handler is None:
            raise ValueError(f"Unknown action: {action}")
        try:
            handler(profile)
        except InnerTubeError as err:
            self.fail(str(err))

    def start(self):
        if not self.profiles:
            xbmcgui.Dialog().ok(self.addon.getAddonInfo("name"), self.tr(S_NO_PROFILE))
            self.addon.openSettings()
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            return None
        if len(self.profiles) == 1:
            try:
                return self.home(self.profiles[0])
            except InnerTubeError as err:
                return self.fail(str(err))
        for profile in self.profiles:
            image = self.media_file(f"profile_{profile.age_group.lower()}.png")
            self.folder(profile.name, self.url(action="home", p=profile.slot), image)
        self.finish(None, self.tr(S_WHO))
        return None

    def home(self, profile):
        categories, _ = catalog.parse_home(self.client(profile).home())
        for cat in categories:
            image = self.media_file(f"category_{cat.asset_key}.png")
            self.folder(cat.title, self.url(action="category", p=profile.slot, c=cat.params), image)
        if profile.search:
            # Not a folder: Kodi runs it outside any listing, so it can open the results.
            self.folder(
                self.tr(S_SEARCH),
                self.url(action="ask", p=profile.slot),
                self.media_file("search.png"),
                is_folder=False,
            )
        self.finish(profile, profile.name)

    def category(self, profile):
        _, page = catalog.parse_home(self.client(profile).home(self.params["c"]))
        self.list_page(profile, page, kind="browse", channel_tiles=True)

    def channel(self, profile):
        page = catalog.parse_channel(self.client(profile).channel(self.params["id"]))
        self.list_page(profile, page, kind="browse")

    def more(self, profile):
        client = self.client(profile)
        kind = self.params["kind"]
        token = self.params["t"]
        if kind == "search":
            page = catalog.parse_continuation(client.search_continuation(token))
        else:
            page = catalog.parse_continuation(client.continuation(token))
        page.title = self.params.get("title", "")
        self.list_page(profile, page, kind=kind)

    def ask(self, profile):
        """Run by RunPlugin (no listing): ask for a query, then open its results.

        The results are their own listing, so going back returns to the profile home
        instead of reopening the keyboard.
        """
        if not profile.search:
            raise ValueError(f"Search is off for profile {profile.slot}")
        keyboard = xbmc.Keyboard("", self.tr(S_SEARCH))
        keyboard.doModal()
        text = keyboard.getText().strip() if keyboard.isConfirmed() else ""
        if text:
            target = self.url(action="search", p=profile.slot, q=text)
            xbmc.executebuiltin(f"Container.Update({target})")

    def search(self, profile):
        if not profile.search:
            raise ValueError(f"Search is off for profile {profile.slot}")
        query = self.params["q"]
        page = catalog.parse_search(self.client(profile).search(query))
        page.title = query
        if not page.items:
            xbmcgui.Dialog().notification(self.addon.getAddonInfo("name"), self.tr(S_NOTHING_FOUND))
        self.list_page(profile, page, kind="search")

    # -- listing ----------------------------------------------------------

    def filter_language(self, profile, page, kind, memory, mode):
        """Drop videos and channels in unwanted languages, topping up from next pages."""
        if mode == language.SHOW_ALL:
            return page
        kept = catalog.Page(title=page.title)
        seen = set()
        for extra in range(MAX_EXTRA_PAGES + 1):
            langs = language.classify(page.items, memory)
            unclear = language.unclear_channels(page.items, langs, memory, PROBE_CHANNELS)
            if unclear:
                self.probe_channels(self.client(profile), unclear, memory)
                langs = language.classify(page.items, memory, learn_first=False)
            for entry in page.items:
                key = getattr(entry, "video_id", None) or entry.channel_id
                if key not in seen and language.keep(langs[id(entry)], mode):
                    seen.add(key)
                    kept.items.append(entry)
            kept.continuation = page.continuation
            if len(kept.items) >= MIN_ITEMS or not page.continuation or extra == MAX_EXTRA_PAGES:
                break
            client = self.client(profile)
            if kind == "search":
                page = catalog.parse_continuation(client.search_continuation(page.continuation))
            else:
                page = catalog.parse_continuation(client.continuation(page.continuation))
        return kept

    def channel_tiles(self, profile, page, memory, mode):
        """Tiles for the channels behind the page's videos, so a category is not only its
        fixed set of about 36 items. Channels already shown, empty in YouTube Kids or in an
        unwanted language are left out."""
        shown = {e.channel_id for e in page.items if isinstance(e, catalog.Channel)}
        candidates = {}
        for entry in page.items:
            if isinstance(entry, catalog.Video) and entry.channel_id and entry.channel:
                if entry.channel_id not in shown:
                    candidates.setdefault(entry.channel_id, entry)
        unknown = [cid for cid in candidates if memory.has_videos(cid) is None]
        if unknown:
            self.probe_channels(self.client(profile), unknown[:PROBE_TILES], memory)
        tiles = []
        for channel_id, video in candidates.items():
            if not memory.has_videos(channel_id):
                continue
            if language.keep(language.channel_language(memory, channel_id), mode):
                tiles.append(catalog.Channel(channel_id, video.channel, thumbnail=video.thumbnail))
        return tiles

    def probe_channels(self, client, channel_ids, memory):
        """Learn the language of channels from their own pages (in parallel)."""

        def fetch(channel_id):
            try:
                return channel_id, catalog.parse_channel(client.channel(channel_id))
            except InnerTubeError as err:
                xbmc.log(f"{LOG_PREFIX} channel {channel_id}: {err}", xbmc.LOGWARNING)
                return channel_id, None

        client.client_version()  # fetch it once, not in every thread
        with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
            results = list(pool.map(fetch, channel_ids))
        for channel_id, page in results:
            if page is None:
                continue  # try again next time
            memory.mark_probed(channel_id, has_videos=bool(page.items))
            # The channel page lists its own videos: all evidence is for this channel.
            for entry in page.items:
                entry.channel_id = channel_id
            language.learn(page.items, memory)

    def play(self, profile):
        """Run by RunPlugin (no listing): play the picked video and queue the ones after it."""
        ids = [v for v in self.params["v"].split(",") if VIDEO_ID.fullmatch(v)]
        if not ids:
            raise ValueError("No video ids to play")
        known = VideoCache(self.data_file("videos.json"))
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        for video_id in ids:
            title, channel, duration = known.get(video_id) or ("", "", 0)
            item = self.video_item(profile, catalog.Video(video_id, title, channel, "", duration))
            item.setProperty("IsPlayable", "true")
            playlist.add(YOUTUBE_PLAY.format(video_id), item)
        xbmc.Player().play(playlist)

    def list_page(self, profile, page, kind, channel_tiles=False):
        mode = language.filter_mode(self.addon.getSettingInt("video_language"), self.locale()[0])
        memory = language.ChannelMemory(self.data_file("channels.json"), profile.age_group)
        page = self.filter_language(profile, page, kind, memory, mode)
        if channel_tiles:
            page.items.extend(self.channel_tiles(profile, page, memory, mode))
        memory.save()
        videos = [e for e in page.items if isinstance(e, catalog.Video)]
        if profile.autoplay:
            VideoCache(self.data_file("videos.json")).remember(videos)
        video_ids = [v.video_id for v in videos]
        for entry in page.items:
            if isinstance(entry, catalog.Video):
                position = video_ids.index(entry.video_id)
                queue = video_ids[position : position + AUTOPLAY_QUEUE]
                self.add_video(profile, entry, queue)
            elif isinstance(entry, catalog.Channel):
                image = entry.banner or entry.thumbnail
                self.folder(
                    entry.title,
                    self.url(action="channel", p=profile.slot, id=entry.channel_id),
                    image,
                    fanart=entry.banner or None,
                )
        if page.continuation:
            self.folder(
                self.tr(S_MORE),
                self.url(
                    action="more", p=profile.slot, kind=kind, t=page.continuation, title=page.title
                ),
                self.media_file("more.png"),
            )
        self.finish(profile, page.title or profile.name)

    def video_item(self, profile, video):
        item = xbmcgui.ListItem(video.title, offscreen=True)
        item.setArt({"thumb": video.thumbnail, "icon": video.thumbnail, "fanart": video.thumbnail})
        tag = item.getVideoInfoTag()
        tag.setMediaType("video")
        tag.setTitle(video.title)
        tag.setDuration(video.duration)
        if not profile.toddler:
            tag.setPlot(video.channel)
            tag.setStudios([video.channel] if video.channel else [])
        return item

    def add_video(self, profile, video, queue):
        item = self.video_item(profile, video)
        if profile.autoplay:
            # Not playable itself: Kodi runs it like RunPlugin and play() starts the queue.
            url = self.url(action="play", p=profile.slot, v=",".join(queue))
        else:
            item.setProperty("IsPlayable", "true")
            url = YOUTUBE_PLAY.format(video.video_id)
        xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=False)


def same_listing(a, b):
    """Kodi reorders query parameters in Container.FolderPath."""
    base_a, _, query_a = a.partition("?")
    base_b, _, query_b = b.partition("?")
    return base_a == base_b and dict(parse_qsl(query_a)) == dict(parse_qsl(query_b))


def kodi_setting(setting_id):
    """A Kodi (not add-on) setting's value over JSON-RPC, or None."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {"setting": setting_id},
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        return response["result"]["value"]
    except (ValueError, KeyError, TypeError):
        xbmc.log(f"{LOG_PREFIX} cannot read Kodi setting {setting_id}", xbmc.LOGWARNING)
        return None


def read_text(path):
    """A file's text (special:// paths too), or None when it does not exist."""
    path = xbmcvfs.translatePath(path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run(argv):
    Plugin(argv).run()
