import pytest

from littlescreen.profiles import find_profile, load_profiles

DEFAULTS = {
    "profile1.enabled": True,
    "profile1.name": "Batole",
    "profile1.age": 0,
    "profile1.style": 0,
    "profile1.search": True,
    "profile1.autoplay": False,
    "profile2.enabled": True,
    "profile2.name": " ",
    "profile2.age": 1,
    "profile2.style": 1,
    "profile2.search": True,
    "profile2.autoplay": False,
    "profile3.enabled": False,
    "profile3.name": "Starší",
    "profile3.age": 2,
    "profile3.style": 1,
    "profile3.search": True,
    "profile3.autoplay": False,
}


def load(settings):
    return load_profiles(settings.__getitem__, settings.__getitem__, settings.__getitem__)


def test_enabled_profiles_only():
    profiles = load(DEFAULTS)
    assert [p.slot for p in profiles] == [1, 2]
    assert profiles[0].age_group == "PRESCHOOL" and profiles[0].toddler
    assert profiles[1].age_group == "YOUNGER" and not profiles[1].toddler


def test_toddler_never_searches():
    assert load(DEFAULTS)[0].search is False
    assert load(DEFAULTS)[1].search is True


def test_blank_name_falls_back_to_slot():
    assert load(DEFAULTS)[1].name == "#2"


def test_out_of_range_age_fails():
    with pytest.raises(ValueError):
        load({**DEFAULTS, "profile1.age": 5})


def test_find_profile():
    profiles = load(DEFAULTS)
    assert find_profile(profiles, 2).name == "#2"
    assert find_profile(profiles, 3) is None


def test_autoplay_setting():
    profiles = load({**DEFAULTS, "profile2.autoplay": True})
    assert [p.autoplay for p in profiles] == [False, True]
