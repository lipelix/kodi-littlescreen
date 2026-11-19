"""Guess whether a video is in the catalogue language, from its title and channel name.

YouTube does not send a video's language. The guess collects evidence, kept under labels
that do not depend on the catalogue language (so it can be remembered per channel):

- language names ("Deutsch", "po slovensky", "українською"): label "name:<code>";
- the scripts a text is written in ("script:CYRILLIC+LATIN"), once per text;
- markers from a pack (packs/): letters and words only one language uses, label "<code>".

`decide` then weighs the evidence against the catalogue language (the target): markers
count only when the target has a complete pack (Czech and Slovak are close, so their
catalogues need them); otherwise only scripts and language names count, which never hide a
video whose language is unclear. A video without evidence takes the language of its
channel, learned from the channel's other titles and remembered between runs.
"""

import json
import re
import unicodedata

from littlescreen.packs import COMPLETE, PACKS

OTHER = "other"  # some language other than the target (and its rival packs)

# Filter modes (setting "video_language"). 1 and 3 were "all but Slovak" and "automatic".
ANY_LANGUAGE = 0
CATALOGUE_LANGUAGE = 2

LANGUAGE_NAME_WEIGHT = 3
CHANNEL_NAME_WEIGHT = 1
CACHE_LIMIT = 3000

NAME = "name:"
SCRIPT = "script:"

# Language names; in a channel name they decide on their own. Lowercase whole words, in the
# language itself: an English name ("Learn Spanish") more often means a lesson in English.
# English, Czech and Slovak names are the exceptions (seen as such in titles).
NAMES = {
    "cs": {"čeština", "češtině", "česky", "český", "česká", "české", "czech", "czechia"},
    "sk": {
        "slovenčina",
        "slovenčine",
        "slovensky",
        "slovenský",
        "slovenská",
        "slovenské",
        "slovak",
        "slovakia",
    },
    "en": {"english"},
    "pl": {"polski", "polska", "polskie", "polsku"},
    "sl": {"slovenščina"},
    "de": {"deutsch", "deutsche", "deutschen"},
    "es": {"español"},
    "fr": {"français"},
    "it": {"italiano"},
    "pt": {"português"},
    "nl": {"nederlands"},
    "hu": {"magyar", "magyarul"},
    "ro": {"română"},
    "tr": {"türkçe"},
    "ru": {"русский", "русском", "русски"},
    "uk": {"українською", "українська", "українські"},
    "he": {"עברית", "israel"},
    "ar": {"العربية", "عربي"},
    "hi": {"हिंदी", "हिन्दी"},
    "bn": {"বাংলা", "bangla"},
    "el": {"ελληνικά"},
}
_NAME_OF = {word: code for code, words in NAMES.items() for word in words}
NAME_PHRASES = ((re.compile(r"\bpo\s+slovensky\b", re.IGNORECASE), "sk"),)

# Scripts of the languages YouTube Kids offers that are not written in Latin letters.
# Names are the first word of a letter's Unicode name (see _script).
SCRIPTS = {
    "ru": {"CYRILLIC"},
    "uk": {"CYRILLIC"},
    "be": {"CYRILLIC"},
    "bg": {"CYRILLIC"},
    "mk": {"CYRILLIC"},
    "sr": {"CYRILLIC", "LATIN"},
    "kk": {"CYRILLIC"},
    "ky": {"CYRILLIC"},
    "mn": {"CYRILLIC"},
    "el": {"GREEK"},
    "he": {"HEBREW"},
    "ar": {"ARABIC"},
    "fa": {"ARABIC"},
    "ur": {"ARABIC"},
    "ja": {"CJK", "KANA"},
    "zh": {"CJK"},
    "ko": {"HANGUL", "CJK"},
    "th": {"THAI"},
    "hi": {"DEVANAGARI"},
    "mr": {"DEVANAGARI"},
    "ne": {"DEVANAGARI"},
    "bn": {"BENGALI"},
    "ta": {"TAMIL"},
    "te": {"TELUGU"},
    "kn": {"KANNADA"},
    "ml": {"MALAYALAM"},
    "gu": {"GUJARATI"},
    "pa": {"GURMUKHI"},
    "ka": {"GEORGIAN"},
    "hy": {"ARMENIAN"},
    "km": {"KHMER"},
    "lo": {"LAO"},
    "my": {"MYANMAR"},
    "si": {"SINHALA"},
    "am": {"ETHIOPIC"},
}
LATIN = {"LATIN"}
_SCRIPT_ALIASES = {
    "IDEOGRAPHIC": "CJK",
    "HIRAGANA": "KANA",
    "KATAKANA": "KANA",
    "KATAKANA-HIRAGANA": "KANA",
}
# Old or other codes YouTube uses for the same language.
_CODE_ALIASES = {"iw": "he", "in": "id", "ji": "yi", "nb": "no"}

_WORD = re.compile(r"[^\W\d_]+")


def target_language(hl):
    """The language code a catalogue `hl` ("de", "pt-BR", "zh-Hant", "iw") filters for."""
    code = re.split(r"[-_]", hl.strip().lower())[0]
    return _CODE_ALIASES.get(code, code)


def scripts_of(code):
    return SCRIPTS.get(code, LATIN)


def _script(char):
    """The script of a letter, by the first word of its Unicode name; None for others."""
    if not unicodedata.category(char).startswith("L"):
        return None  # digits like ½ match _WORD too
    words = unicodedata.name(char, "").split()
    if words and words[0] in ("FULLWIDTH", "HALFWIDTH"):
        words = words[1:]
    if not words or words[0] == "MODIFIER":
        return None
    return _SCRIPT_ALIASES.get(words[0], words[0])


def _marker(word):
    """The pack whose marker the (Latin) word is, or None."""
    low = word.lower()
    chars = set(word)
    for pack in PACKS:
        if chars & pack.letters:
            return pack.code
    for pack in PACKS:
        if low in pack.words:
            return pack.code
    for pack in PACKS:
        if any(pattern.fullmatch(low) for pattern in pack.patterns):
            return pack.code
    return None


def score(text, weight=1, name_weight=LANGUAGE_NAME_WEIGHT):
    """Evidence {label: count} for a piece of text, whatever the catalogue language."""
    counts = {}

    def count(label, value):
        counts[label] = counts.get(label, 0) + value

    scripts = set()
    for word in _WORD.findall(text):
        word_scripts = {_script(c) for c in word} - {None}
        scripts |= word_scripts
        name = _NAME_OF.get(word.lower())
        if name:
            count(NAME + name, name_weight)
        elif word_scripts == LATIN:
            marker = _marker(word)
            if marker:
                count(marker, weight)
    for phrase, code in NAME_PHRASES:
        if phrase.search(text):
            count(NAME + code, name_weight)
    if scripts:
        count(SCRIPT + "+".join(sorted(scripts)), weight)
    return counts


def add(a, b):
    return {label: a.get(label, 0) + b.get(label, 0) for label in {*a, *b}}


def _side(label, target):
    """Which language a piece of evidence speaks for, seen from the target: the target,
    a rival with a complete pack, OTHER, or None (no say)."""
    if label.startswith(SCRIPT):
        scripts = set(label[len(SCRIPT) :].split("+"))
        # Latin brand names turn up in titles of any script; other scripts tell more.
        if scripts - LATIN:
            scripts -= LATIN
        if scripts & scripts_of(target):
            # The target's script: the markers decide between languages that share it.
            return None if target in COMPLETE else target
        return OTHER
    if label.startswith(NAME):
        code = label[len(NAME) :]
    elif target in COMPLETE:
        code = label  # a marker ("other" in files from 0.4: some language not cs/sk)
    else:
        return None  # markers are for languages with complete packs only
    if code == target or (code in COMPLETE and target in COMPLETE):
        return code
    return OTHER


def decide(counts, target, margin=1):
    """The language the evidence points to (the target, a rival pack language or OTHER)
    if it leads by at least `margin`, else None."""
    sides = {}
    for label, value in counts.items():
        side = _side(label, target)
        if side and value:
            sides[side] = sides.get(side, 0) + value
    ranked = sorted(sides.items(), key=lambda kv: kv[1], reverse=True) + [(None, 0)] * 2
    (best, first), (_, second) = ranked[0], ranked[1]
    return best if first - second >= margin else None


def item_score(title, channel):
    return add(score(title), score(channel, CHANNEL_NAME_WEIGHT, LANGUAGE_NAME_WEIGHT * 2))


class ChannelMemory:
    """Evidence per channel id, kept in a JSON file between runs.

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
            merged = {label: value // 2 for label, value in merged.items()}
        self.data.pop(channel_id, None)
        self.data[channel_id] = {label: value for label, value in merged.items() if value}
        while len(self.data) > CACHE_LIMIT:  # newest last, so trimming drops the oldest
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
    """Add the items' evidence to their channels' evidence."""
    for item in items:
        memory.learn(getattr(item, "channel_id", ""), _own_counts(item))


def classify(items, memory, target, learn_first=True):
    """Language per item (video or channel) as seen from `target`, keyed by id(item).

    Decides each item from its own evidence or, when it is not decisive, from its
    channel's evidence (by default first learned from these items).
    """
    if learn_first:
        learn(items, memory)
    result = {}
    for item in items:
        lang = decide(_own_counts(item), target)
        if lang is None:
            lang = decide(memory.get(getattr(item, "channel_id", "")), target)
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


def channel_language(memory, channel_id, target):
    return decide(memory.get(channel_id), target)


def filter_mode(setting):
    """The filter for the `video_language` setting (values of earlier versions included)."""
    return ANY_LANGUAGE if setting == ANY_LANGUAGE else CATALOGUE_LANGUAGE


def keep(lang, mode, target):
    if mode == ANY_LANGUAGE:
        return True
    if mode == CATALOGUE_LANGUAGE:
        return lang in (target, None)
    raise ValueError(f"Unknown language filter mode: {mode}")
