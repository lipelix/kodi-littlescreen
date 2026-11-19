"""Minimal fake Kodi modules (xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs) for tests."""

import json
import sys
import types

STATE = {}


def reset(
    settings,
    path,
    profile_dir,
    skin="skin.estuary",
    keyboard=None,
    folder_path=None,
    kodi_settings=None,
    kodi_language="en",
):
    STATE.clear()
    STATE.update(
        settings=settings,
        path=path,
        profile=profile_dir,
        skin=skin,
        items=[],
        ended=None,
        builtins=[],
        notifications=[],
        content=None,
        category=None,
        keyboard=keyboard,
        dialogs=[],
        opened_settings=False,
        folder_path=folder_path,
        kodi_settings=kodi_settings or {},
        kodi_language=kodi_language,
    )


class ListItem:
    def __init__(self, label="", offscreen=False):
        self.label = label
        self.art = {}
        self.props = {}
        self.tag = InfoTag()

    def setArt(self, art):
        self.art.update(art)

    def setProperty(self, key, value):
        self.props[key] = value

    def getVideoInfoTag(self):
        return self.tag


class InfoTag:
    def __init__(self):
        self.data = {}

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda value: self.data.__setitem__(name[3:].lower(), value)
        raise AttributeError(name)


class Addon:
    def getSettingBool(self, key):
        return bool(STATE["settings"][key])

    def getSettingInt(self, key):
        return int(STATE["settings"][key])

    def getSettingString(self, key):
        return str(STATE["settings"][key])

    def getLocalizedString(self, string_id):
        return f"#{string_id}"

    def getAddonInfo(self, key):
        return {"path": STATE["path"], "profile": STATE["profile"], "name": "Little Screen"}[key]

    def openSettings(self):
        STATE["opened_settings"] = True


class Dialog:
    def notification(self, heading, message, icon=None, time=0):
        STATE["notifications"].append(message)

    def ok(self, heading, message):
        STATE["dialogs"].append(message)


class Keyboard:
    def __init__(self, default="", heading=""):
        pass

    def doModal(self):
        pass

    def isConfirmed(self):
        return STATE["keyboard"] is not None

    def getText(self):
        return STATE["keyboard"] or ""


def execute_jsonrpc(request):
    request = json.loads(request)
    assert request["method"] == "Settings.GetSettingValue", request
    setting = request["params"]["setting"]
    if setting not in STATE["kodi_settings"]:
        return json.dumps({"id": 1, "jsonrpc": "2.0", "error": {"code": -32602}})
    return json.dumps(
        {"id": 1, "jsonrpc": "2.0", "result": {"value": STATE["kodi_settings"][setting]}}
    )


class PlayList:
    def __init__(self, kind):
        STATE.setdefault("playlist", [])

    def clear(self):
        STATE["playlist"] = []

    def add(self, url, item=None):
        STATE["playlist"].append((url, item))


class Player:
    def play(self, item=None):
        STATE["played"] = item


def install():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 4
    xbmc.ISO_639_1 = 0
    xbmc.getLanguage = lambda fmt=None, region=False: STATE["kodi_language"]
    xbmc.executeJSONRPC = execute_jsonrpc
    xbmc.log = lambda msg, level=0: None
    xbmc.getSkinDir = lambda: STATE["skin"]
    xbmc.executebuiltin = lambda cmd: STATE["builtins"].append(cmd)
    xbmc.Keyboard = Keyboard
    xbmc.PlayList = PlayList
    xbmc.Player = Player
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.sleep = lambda ms: STATE.__setitem__("slept", STATE.get("slept", 0) + ms)
    xbmc.getInfoLabel = lambda label: (
        (STATE["folder_path"] or "") if label == "Container.FolderPath" else ""
    )

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.ListItem = ListItem
    xbmcgui.Dialog = Dialog
    xbmcgui.NOTIFICATION_ERROR = "error"

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.addDirectoryItem = lambda handle, url, item, isFolder=False: STATE["items"].append(
        (url, item, isFolder)
    )
    xbmcplugin.endOfDirectory = lambda handle, succeeded=True, cacheToDisc=True: STATE.__setitem__(
        "ended", succeeded
    )
    xbmcplugin.setContent = lambda handle, content: STATE.__setitem__("content", content)
    xbmcplugin.setPluginCategory = lambda handle, cat: STATE.__setitem__("category", cat)
    xbmcplugin.SORT_METHOD_UNSORTED = 0
    xbmcplugin.addSortMethod = lambda handle, method, labelMask="", label2Mask="": STATE.update(
        sort=method, label_mask=labelMask, label2_mask=label2Mask
    )

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = Addon

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda p: p
    xbmcvfs.mkdirs = lambda p: True

    for mod in (xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs):
        sys.modules[mod.__name__] = mod
