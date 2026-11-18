"""Minimal fake Kodi modules (xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs) for tests."""

import sys
import types

STATE = {}


def reset(settings, path, profile_dir, skin="skin.estuary", keyboard=None, folder_path=None):
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
    xbmc.LOGERROR = 4
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
    xbmcplugin.addSortMethod = lambda handle, method: STATE.__setitem__("sort", method)

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = Addon

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda p: p
    xbmcvfs.mkdirs = lambda p: True

    for mod in (xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs):
        sys.modules[mod.__name__] = mod
