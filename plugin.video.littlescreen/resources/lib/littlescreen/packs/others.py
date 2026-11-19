"""Small marker lists for languages that turn up in the Czech and Slovak catalogues.

Not enough to filter an English, Polish or Slovenian catalogue (incomplete packs), only
evidence that a title is in neither Czech nor Slovak.
"""

EN = "en"
EN_WORDS = frozenset(
    {
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
    }
)

PL = "pl"
PL_LETTERS = frozenset("łęąśćźżńŁĘĄŚĆŹŻŃ")
PL_WORDS = frozenset({"dla", "dzieci", "się", "przed", "jest"})

SL = "sl"
SL_WORDS = frozenset({"otroke", "pesmice"})
