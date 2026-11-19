"""Draw the add-on artwork: icon, fanart and 16:9 tiles for categories and profiles.

The icon and fanart are copied to repository.littlescreen too.

Run with Pillow installed: .venv/bin/python scripts/make_media.py
Tiles are 16:9 because Estuary's Wall view shows video thumbnails in that shape.
"""

import math
import os
import random
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), "..", "plugin.video.littlescreen", "resources")
REPOSITORY = os.path.join(os.path.dirname(__file__), "..", "repository.littlescreen")
MEDIA = os.path.join(ROOT, "media")
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
SS = 4  # supersampling
W, H = 640, 360
WHITE = (255, 255, 255, 255)

# Colours from the YouTube Kids API (categoryAssets.backgroundColor).
CATEGORY_COLORS = {
    "shows": "#2E5FD8",
    "music": "#FED51C",
    "learning": "#CC26A1",
    "explore": "#39A695",
    "gaming": "#67C0FF",
}
PROFILE_COLORS = {"preschool": "#FF8A65", "younger": "#7E57C2", "tween": "#26A69A"}


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (255,)


def shade(rgb, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in rgb[:3]) + (255,)


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def card(color, w=W, h=H, radius=48):
    """Rounded card with a soft top-to-bottom gradient."""
    img = canvas(w, h)
    top, bottom = shade(color, 1.12), shade(color, 0.86)
    grad = Image.new("RGBA", img.size)
    gd = ImageDraw.Draw(grad)
    for y in range(img.size[1]):
        t = y / img.size[1]
        gd.line(
            [(0, y), (img.size[0], y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,),
        )
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, img.size[0] - 1, img.size[1] - 1], radius * SS, fill=255
    )
    img.paste(grad, (0, 0), mask)
    return img


def glyph_color(color):
    # Dark glyph on light backgrounds (yellow), white elsewhere.
    r, g, b = color[:3]
    return (40, 40, 60, 255) if (0.299 * r + 0.587 * g + 0.114 * b) > 186 else WHITE


def save(img, name, size=(W, H)):
    out = img.resize(size, Image.LANCZOS)
    path = os.path.join(MEDIA if not name.startswith("../") else ROOT, name.replace("../", ""))
    if path.endswith(".jpg"):
        out.convert("RGB").save(path, quality=88)
    else:
        out.save(path, optimize=True)


def s(v):
    return v * SS


# -- glyphs (coordinates on the 640x360 card, centre 320,180) ---------------


def g_tv(d, c):
    d.line([s(270), s(70), s(305), s(105)], fill=c, width=s(12))
    d.line([s(370), s(70), s(335), s(105)], fill=c, width=s(12))
    d.rounded_rectangle([s(205), s(105), s(435), s(285)], s(30), outline=c, width=s(16))
    d.polygon([(s(295), s(150)), (s(295), s(240)), (s(370), s(195))], fill=c)


def g_music(d, c):
    d.ellipse([s(215), s(225), s(285), s(280)], fill=c)
    d.ellipse([s(355), s(200), s(425), s(255)], fill=c)
    d.rectangle([s(272), s(105), s(287), s(255)], fill=c)
    d.rectangle([s(412), s(80), s(427), s(230)], fill=c)
    d.polygon([(s(272), s(105)), (s(427), s(80)), (s(427), s(115)), (s(272), s(140))], fill=c)


def g_letters(d, c):
    font = ImageFont.truetype(FONT, s(150))
    d.text((s(320), s(185)), "ABC", font=font, fill=c, anchor="mm")


def g_compass(d, c):
    d.ellipse([s(225), s(85), s(415), s(275)], outline=c, width=s(16))
    d.polygon([(s(320), s(110)), (s(345), s(180)), (s(320), s(250)), (s(295), s(180))], fill=c)
    d.ellipse([s(310), s(170), s(330), s(190)], fill=(0, 0, 0, 0))


def g_gamepad(d, c):
    d.rounded_rectangle([s(185), s(115), s(455), s(255)], s(70), fill=c)
    hole = (0, 0, 0, 0)
    d.rectangle([s(230), s(172), s(290), s(194)], fill=hole)
    d.rectangle([s(249), s(153), s(271), s(213)], fill=hole)
    d.ellipse([s(360), s(150), s(390), s(180)], fill=hole)
    d.ellipse([s(390), s(185), s(420), s(215)], fill=hole)


def g_magnifier(d, c):
    d.ellipse([s(230), s(80), s(370), s(220)], outline=c, width=s(20))
    d.line([s(352), s(202), s(420), s(275)], fill=c, width=s(30))


def g_arrow(d, c):
    d.rounded_rectangle([s(200), s(155), s(360), s(205)], s(20), fill=c)
    d.polygon([(s(340), s(95)), (s(450), s(180)), (s(340), s(265))], fill=c)


def g_play(d, c):
    d.polygon([(s(275), s(100)), (s(275), s(260)), (s(410), s(180))], fill=c)


def g_face(age):
    def draw(d, c):
        skin = (255, 224, 189, 255)
        hair = (92, 64, 51, 255)
        r = {"preschool": 80, "younger": 92, "tween": 100}[age]
        cx, cy = 320, 190
        if age == "tween":
            d.ellipse([s(cx - r - 8), s(cy - r - 10), s(cx + r + 8), s(cy + r - 20)], fill=hair)
        d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=skin)
        if age == "preschool":
            d.arc(
                [s(cx - 22), s(cy - r - 30), s(cx + 18), s(cy - r + 10)],
                200,
                20,
                fill=hair,
                width=s(9),
            )
        else:
            d.pieslice([s(cx - r), s(cy - r), s(cx + r), s(cy + r - 20)], 180, 360, fill=hair)
        eye = r * 0.36
        for dx in (-eye, eye):
            d.ellipse(
                [s(cx + dx - 9), s(cy - 4), s(cx + dx + 9), s(cy + 14)], fill=(50, 40, 40, 255)
            )
        d.arc(
            [s(cx - r * 0.4), s(cy + 5), s(cx + r * 0.4), s(cy + r * 0.62)],
            20,
            160,
            fill=(200, 70, 70, 255),
            width=s(8),
        )
        for dx in (-r * 0.6, r * 0.6):
            d.ellipse(
                [s(cx + dx - 14), s(cy + 22), s(cx + dx + 14), s(cy + 42)],
                fill=(255, 150, 150, 200),
            )

    return draw


def tile(color_hex, glyph, name):
    color = hex_rgb(color_hex)
    img = card(color)
    layer = canvas(W, H)
    glyph(ImageDraw.Draw(layer), glyph_color(color))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(layer.getchannel("A").point(lambda a: a * 0.25))
    shadow = shadow.filter(ImageFilter.GaussianBlur(s(6)))
    img.alpha_composite(shadow, (0, s(6)))
    # Punch holes drawn as transparent pixels back to the card colour.
    img.alpha_composite(layer)
    save(img, name)


def icon():
    img = card(hex_rgb("#FF6B4A"), 512, 512, radius=0)
    d = ImageDraw.Draw(img)
    d.polygon([(s(200), s(150)), (s(200), s(362)), (s(380), s(256))], fill=WHITE)
    # Little star, for the "kids" part.
    cx, cy, ro, ri = 390, 130, 52, 22
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = ro if i % 2 == 0 else ri
        pts.append((s(cx + r * math.cos(a)), s(cy + r * math.sin(a))))
    d.polygon(pts, fill=hex_rgb("#FED51C"))
    save(img, "../icon.png", (512, 512))


def fanart():
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), hex_rgb("#1B2A4A"))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(27 + 20 * t), int(42 + 10 * t), int(74 + 30 * t), 255))
    rnd = random.Random(7)
    dots = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    colors = list(CATEGORY_COLORS.values()) + list(PROFILE_COLORS.values())
    for _ in range(70):
        r = rnd.randint(10, 60)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        c = hex_rgb(rnd.choice(colors))[:3] + (70,)
        dd.ellipse([x - r, y - r, x + r, y + r], fill=c)
    img.alpha_composite(dots.filter(ImageFilter.GaussianBlur(3)))
    img.convert("RGB").save(os.path.join(ROOT, "fanart.jpg"), quality=85)


def main():
    os.makedirs(MEDIA, exist_ok=True)
    glyphs = {
        "shows": g_tv,
        "music": g_music,
        "learning": g_letters,
        "explore": g_compass,
        "gaming": g_gamepad,
    }
    for key, glyph in glyphs.items():
        tile(CATEGORY_COLORS[key], glyph, f"category_{key}.png")
    for age, color in PROFILE_COLORS.items():
        tile(color, g_face(age), f"profile_{age}.png")
    tile("#FF6B4A", g_magnifier, "search.png")
    tile("#5C6BC0", g_arrow, "more.png")
    tile("#90A4AE", g_play, "default.png")
    icon()
    fanart()
    # The repository add-on wears the same artwork.
    for name in ("icon.png", "fanart.jpg"):
        shutil.copyfile(os.path.join(ROOT, name), os.path.join(REPOSITORY, name))


if __name__ == "__main__":
    main()
