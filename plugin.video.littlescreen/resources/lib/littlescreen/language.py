"""Guess the language of a video from its title and channel name: Czech, Slovak or other.

YouTube does not send a video's language, and the CZ catalogue mixes Czech and Slovak.
The two are close, so the guess counts markers: letters only one of them uses, common
words that differ, and explicit language names ("Čeština", "po slovensky", "Polski").
A video without markers takes the language of its channel, learned from the channel's
other titles and remembered between runs.
"""

import json
import re
import unicodedata

CS = "cs"
SK = "sk"
OTHER = "other"
LANGS = (CS, SK, OTHER)

# Filter modes (setting "video_language").
SHOW_ALL = 0
HIDE_SLOVAK = 1
CZECH_ONLY = 2
AUTOMATIC = 3  # Czech only for a Czech catalogue, otherwise everything

LANGUAGE_NAME_WEIGHT = 3
CHANNEL_NAME_WEIGHT = 1
CACHE_LIMIT = 3000

_CS_CHARS = set("ěřůĚŘŮ")
_SK_CHARS = set("äôľĺŕÄÔĽĹŔ")
_PL_CHARS = set("łęąśćźżńŁĘĄŚĆŹŻŃ")

_CS_WORDS = {
    "pro",
    "dětské",
    "dětský",
    "dětská",
    "písničky",
    "písnička",
    "písničku",
    "písně",
    "pohádka",
    "pohádky",
    "pohádku",
    "pohádkové",
    "pohádkový",
    "zpívánky",
    "zpívaná",
    "říkanky",
    "jsem",
    "jsme",
    "jsou",
    "jak",
    "který",
    "která",
    "které",
    "se",
    "ve",
    "co",
    "když",
    "kamarádi",
    "díl",
    "díly",
    "oficiální",
    "jen",
    "také",
    "není",
    "ještě",
    "naučit",
    "pejsek",
    "dobrou",
    "hraček",
    "jaká",
    "jaké",
    "jaký",
    "mám",
    "máme",
}
_SK_WORDS = {
    "pre",
    "deti",
    "detské",
    "detský",
    "detská",
    "pesničky",
    "pesnička",
    "pesničku",
    "pesničiek",
    "rozprávka",
    "rozprávky",
    "rozprávku",
    "rozpravka",
    "rozpravky",
    "riekanky",
    "sa",
    "ako",
    "keď",
    "čo",
    "vo",
    "som",
    "sme",
    "aj",
    "alebo",
    "ktorý",
    "ktorá",
    "ktoré",
    "diel",
    "oficiálny",
    "najlepšie",
    "zbierka",
    "kamaráti",
    "dobrú",
    "nie",
    "sú",
    "spievankovo",
    "farebný",
    "detí",
    "predstavenie",
    "hasičov",
    "lebo",
    "ďalšie",
    "najpopulárnejšie",
    "rozlúčka",
    "návšteve",
    "stratená",
    "príbeh",
    "príbehy",
    "svet",
    "tri",
    "sedem",
    "hviezda",
    "hviezdy",
    "hviezdička",
    "vianočný",
    "vianočná",
    "vianoce",
    "zvieratká",
    "zvieratá",
    "zvieratko",
    "pieseň",
    "piesne",
    "piesničky",
    "mesiac",
    "dieťa",
    "deťom",
    "čarovná",
    "čarovný",
    "veselý",
}
_OTHER_WORDS = {
    # English
    "the",
    "and",
    "for",
    "with",
    "from",
    "kids",
    "song",
    "songs",
    "nursery",
    "rhymes",
    "official",
    "learn",
    "baby",
    # Polish
    "dla",
    "dzieci",
    "się",
    "przed",
    "jest",
    # Slovenian
    "otroke",
    "pesmice",
}
# Language names; in a channel name they decide on their own.
_CS_NAMES = {"čeština", "češtině", "česky", "český", "česká", "české", "czech", "czechia"}
_SK_NAMES = {
    "slovenčina",
    "slovenčine",
    "slovensky",
    "slovenský",
    "slovenská",
    "slovenské",
    "slovak",
    "slovakia",
}
_OTHER_NAMES = {
    "polski",
    "polska",
    "english",
    "slovenščina",
    "deutsch",
    "español",
    "français",
    "israel",
    "русский",
}

_AMBIGUOUS = _CS_WORDS & _SK_WORDS  # must stay empty; checked by the tests
_SK_INFINITIVE = re.compile(r"\w{2,}(?:iť|ať|ovať|uť|núť|ieť|ýť)$")
_WORD = re.compile(r"[^\W\d_]+")


def _is_latin(char):
    return "LATIN" in unicodedata.name(char, "")


def score(text, weight=1, name_weight=LANGUAGE_NAME_WEIGHT):
    """Return {cs, sk, other} marker counts for a piece of text."""
    counts = {CS: 0, SK: 0, OTHER: 0}
    for word in _WORD.findall(text):
        low = word.lower()
        chars = set(word)
        if not all(_is_latin(c) for c in word):
            counts[OTHER] += weight
            continue
        if low in _CS_NAMES:
            counts[CS] += name_weight
        elif low in _SK_NAMES:
            counts[SK] += name_weight
        elif low in _OTHER_NAMES:
            counts[OTHER] += name_weight
        elif chars & _CS_CHARS:
            counts[CS] += weight
        elif chars & _SK_CHARS:
            counts[SK] += weight
        elif chars & _PL_CHARS:
            counts[OTHER] += weight
        elif low in _AMBIGUOUS:
            continue
        elif low in _CS_WORDS:
            counts[CS] += weight
        elif low in _SK_WORDS or _SK_INFINITIVE.match(low):
            counts[SK] += weight
        elif low in _OTHER_WORDS:
            counts[OTHER] += weight
    if re.search(r"\bpo\s+slovensky\b", text, re.IGNORECASE):
        counts[SK] += name_weight
    return counts


def add(a, b):
    return {lang: a.get(lang, 0) + b.get(lang, 0) for lang in LANGS}


def decide(counts, margin=1):
    """The leading language if it leads by at least `margin`, else None."""
    ranked = sorted(LANGS, key=lambda lang: counts.get(lang, 0), reverse=True)
    best, second = ranked[0], ranked[1]
    if counts.get(best, 0) - counts.get(second, 0) >= margin:
        return best
    return None


def item_score(title, channel):
    return add(score(title), score(channel, CHANNEL_NAME_WEIGHT, LANGUAGE_NAME_WEIGHT * 2))


class ChannelMemory:
    """Marker counts per channel id, kept in a JSON file between runs.

    Also remembers which channels had their own page read ("probed") and whether it
    listed any videos, so each channel is looked up at most once.
    """

    def __init__(self, path, scope=""):
        self.path = path
        # What a channel page lists depends on the age group, so probes are kept per scope.
        self.scope = scope
        self.data = {}
        self.probed = {}
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            if isinstance(loaded.get("counts"), dict):
                self.data = loaded["counts"]
                probed = loaded.get("probed", {})
                if isinstance(probed, list):  # 0.2.0: ids only, videos unknown
                    probed = dict.fromkeys(probed, True)
                self.probed = {cid: bool(has) for cid, has in probed.items()}
            else:  # 0.2.0 kept the counts only
                self.data = loaded
        self.dirty = False

    def get(self, channel_id):
        return self.data.get(channel_id, {})

    def learn(self, channel_id, counts):
        if not channel_id or not any(counts.values()):
            return
        merged = add(self.get(channel_id), counts)
        # Keep counts small so a channel can change its mind.
        while max(merged.values()) > 50:
            merged = {lang: value // 2 for lang, value in merged.items()}
        self.data.pop(channel_id, None)
        self.data[channel_id] = merged  # newest last, so trimming drops the oldest
        while len(self.data) > CACHE_LIMIT:
            self.data.pop(next(iter(self.data)))
        self.dirty = True

    def _probe_key(self, channel_id):
        return f"{self.scope}:{channel_id}" if self.scope else channel_id

    def was_probed(self, channel_id):
        return self._probe_key(channel_id) in self.probed

    def has_videos(self, channel_id):
        """True/False once the channel page was read, None before."""
        return self.probed.get(self._probe_key(channel_id))

    def mark_probed(self, channel_id, has_videos=True):
        key = self._probe_key(channel_id)
        self.probed.pop(key, None)
        self.probed[key] = bool(has_videos)
        while len(self.probed) > CACHE_LIMIT:
            self.probed.pop(next(iter(self.probed)))
        self.dirty = True

    def save(self):
        if not self.dirty:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"counts": self.data, "probed": self.probed}, fh, ensure_ascii=False)
        except OSError:
            pass  # a lost cache only makes the next guesses weaker


def _own_counts(item):
    if hasattr(item, "video_id"):
        return item_score(item.title, item.channel)
    # A channel tile: its name is all there is.
    return score(item.title, CHANNEL_NAME_WEIGHT, LANGUAGE_NAME_WEIGHT * 2)


def learn(items, memory):
    """Add the items' markers to their channels' evidence."""
    for item in items:
        memory.learn(getattr(item, "channel_id", ""), _own_counts(item))


def classify(items, memory, learn_first=True):
    """Language per item (video or channel), keyed by id(item).

    Decides each item from its own markers or, when they are not decisive, from its
    channel's evidence (by default first learned from these items).
    """
    if learn_first:
        learn(items, memory)
    result = {}
    for item in items:
        lang = decide(_own_counts(item))
        if lang is None:
            lang = decide(memory.get(getattr(item, "channel_id", "")))
        result[id(item)] = lang
    return result


def unclear_channels(items, result, memory, limit):
    """Channels of undecided items that have not been looked up yet, at most `limit`."""
    found = []
    for item in items:
        channel_id = getattr(item, "channel_id", "")
        if (
            result[id(item)] is None
            and channel_id
            and channel_id not in found
            and not memory.was_probed(channel_id)
        ):
            found.append(channel_id)
    return found[:limit]


def channel_language(memory, channel_id):
    return decide(memory.get(channel_id))


def filter_mode(setting, hl):
    """The filter for the `video_language` setting, given the catalogue language `hl`."""
    if setting != AUTOMATIC:
        return setting
    return CZECH_ONLY if hl.split("-")[0].lower() == CS else SHOW_ALL


def keep(lang, mode):
    if mode == SHOW_ALL:
        return True
    if mode == HIDE_SLOVAK:
        return lang != SK
    if mode == CZECH_ONLY:
        return lang in (CS, None)
    raise ValueError(f"Unknown language filter mode: {mode}")
