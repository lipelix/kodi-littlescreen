"""Viewer profiles stored in the add-on settings (up to three)."""

from dataclasses import dataclass

from littlescreen.innertube import AGE_GROUPS

PROFILE_SLOTS = (1, 2, 3)
STYLE_TODDLER = "toddler"
STYLE_LIST = "list"
STYLES = (STYLE_TODDLER, STYLE_LIST)


@dataclass
class Profile:
    slot: int
    name: str
    age_group: str
    style: str
    search: bool
    autoplay: bool = False

    @property
    def toddler(self):
        return self.style == STYLE_TODDLER


def load_profiles(get_bool, get_int, get_string, age_label):
    """Read enabled profiles with the given settings getters (setting id -> value).

    A profile without a name is called by its age group: `age_label(age_group)`.
    """
    profiles = []
    for slot in PROFILE_SLOTS:
        prefix = f"profile{slot}."
        if not get_bool(prefix + "enabled"):
            continue
        age = get_int(prefix + "age")
        style = get_int(prefix + "style")
        if not 0 <= age < len(AGE_GROUPS):
            raise ValueError(f"Setting {prefix}age out of range: {age}")
        if not 0 <= style < len(STYLES):
            raise ValueError(f"Setting {prefix}style out of range: {style}")
        profiles.append(
            Profile(
                slot=slot,
                name=get_string(prefix + "name").strip() or age_label(AGE_GROUPS[age]),
                age_group=AGE_GROUPS[age],
                style=STYLES[style],
                search=get_bool(prefix + "search") and STYLES[style] != STYLE_TODDLER,
                autoplay=get_bool(prefix + "autoplay"),
            )
        )
    return profiles


def find_profile(profiles, slot):
    for profile in profiles:
        if profile.slot == slot:
            return profile
    return None
