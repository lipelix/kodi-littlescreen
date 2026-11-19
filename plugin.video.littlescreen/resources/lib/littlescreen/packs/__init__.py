"""Marker packs: letters, words and word patterns that point to one language.

A pack is "complete" when its markers, together with the other packs, are good enough to
filter a catalogue in its language; only then are markers used at all (see language.py).
Incomplete packs only add evidence against a complete one (English words in a Czech
catalogue, for example).

How to add a pack: AGENTS.md, "Language filter".
"""

from dataclasses import dataclass

from littlescreen.packs import cs, others, sk


@dataclass(frozen=True)
class Pack:
    code: str  # ISO 639-1, as YouTube's `hl` without the region
    letters: frozenset = frozenset()  # letters no other pack uses
    words: frozenset = frozenset()  # lowercase whole words no other pack uses
    patterns: tuple = ()  # compiled regexes, fullmatch on a lowercase word
    complete: bool = True


PACKS = (
    Pack(cs.CODE, cs.LETTERS, cs.WORDS),
    Pack(sk.CODE, sk.LETTERS, sk.WORDS, sk.PATTERNS),
    Pack(others.EN, words=others.EN_WORDS, complete=False),
    Pack(others.PL, others.PL_LETTERS, others.PL_WORDS, complete=False),
    Pack(others.SL, words=others.SL_WORDS, complete=False),
)
COMPLETE = frozenset(pack.code for pack in PACKS if pack.complete)
