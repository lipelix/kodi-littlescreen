"""Catalogue language (`hl`) and region (`gl`): the add-on settings, or else Kodi's own.

Kodi's interface language is a language add-on (`locale.language`, e.g.
`resource.language.de_de`); its region (`locale.country`) is the name of one of the
`<region>` entries in that add-on's `langinfo.xml`, whose `locale` attribute is the ISO 3166
code. When that cannot be read, the country part of the language add-on id is used.
"""

import re
import xml.etree.ElementTree as ET

FALLBACK_HL = "en"
FALLBACK_GL = "US"
LANGINFO = "{root}/{addon}/resources/langinfo.xml"
ADDON_ROOTS = ("special://home/addons", "special://xbmc/addons")

_LANGUAGE_ADDON = re.compile(r"resource\.language\.([a-z]{2,3})(?:_([a-z]{2}))?(?:@\w+)?")
_GL = re.compile(r"[A-Z]{2}")
# Languages whose written form differs by country: YouTube needs the region in `hl`.
_HL_WITH_REGION = {("zh", "TW"), ("zh", "HK"), ("pt", "PT"), ("fr", "CA"), ("en", "GB")}
# Kodi interface languages the YouTube Kids API takes as `hl` (checked 2026-11-19); others
# (cy, eo, fo, mi, mt, oc, os, tg, ast, ...) get HTTP 400, so they fall back to English.
YOUTUBE_LANGUAGES = frozenset(
    "af am ar az be bg bs ca cs da de el en es et eu fa fi fr gl he hi hr hu hy id is it ja "
    "kn ko lt lv mk ml mn ms my nb nl no pl pt ro ru si sk sl sq sr sv ta te th tr uk uz vi "
    "zh".split()
)


def language_addon_parts(addon_id):
    """("de", "DE") for `resource.language.de_de`; None parts when the id does not say."""
    match = _LANGUAGE_ADDON.fullmatch(addon_id or "")
    if not match:
        return None, None
    language, country = match.groups()
    return language, country.upper() if country else None


def region_from_langinfo(xml_text, region_name):
    """ISO 3166 code (`locale`) of the named region in a Kodi `langinfo.xml`, or None."""
    if not xml_text or not region_name:
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for region in root.iter("region"):
        if region.get("name") == region_name:
            code = (region.get("locale") or "").upper()
            return code if _GL.fullmatch(code) else None
    return None


def kodi_language(iso_639_1, language_addon):
    """`hl` for Kodi's interface language: its ISO 639-1 code, with the country where
    YouTube writes the language differently (zh-TW, pt-PT, ...). None when YouTube Kids
    does not offer the language."""
    addon_language, country = language_addon_parts(language_addon)
    language = (iso_639_1 or "").strip().lower() or addon_language
    if language not in YOUTUBE_LANGUAGES:
        return None
    if (language, country) in _HL_WITH_REGION:
        return f"{language}-{country}"
    return language


def kodi_region(language_addon, region_name, read_file):
    """`gl` for Kodi's region setting; `read_file(path)` returns a file's text or None."""
    for root in ADDON_ROOTS:
        code = region_from_langinfo(
            read_file(LANGINFO.format(root=root, addon=language_addon)), region_name
        )
        if code:
            return code
    return language_addon_parts(language_addon)[1]


def resolve(hl_setting, gl_setting, kodi_hl, kodi_gl):
    """(hl, gl) to use: a manual setting wins, an empty one follows Kodi.

    `kodi_hl` and `kodi_gl` are callables, so Kodi is only asked when a setting is empty.
    """
    hl = (hl_setting or "").strip() or kodi_hl() or FALLBACK_HL
    gl = (gl_setting or "").strip().upper() or kodi_gl() or FALLBACK_GL
    return hl, gl
