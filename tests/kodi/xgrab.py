"""Save the X display (Xvfb) as a PNG with libX11 through ctypes: no extra packages.

Kodi's own TakeScreenshot crashes under Xvfb (software GL), so the screenshots are read
from the X server instead. Usage: xgrab.py OUT.png  (display from $DISPLAY)
"""

import ctypes
import ctypes.util
import struct
import sys
import zlib

ZPIXMAP = 2
ALL_PLANES = 0xFFFFFFFF


class XImage(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("xoffset", ctypes.c_int),
        ("format", ctypes.c_int),
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("byte_order", ctypes.c_int),
        ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int),
        ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int),
        ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong),
        ("blue_mask", ctypes.c_ulong),
    ]


class XWindowAttributes(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]
    _fields_ += [("width", ctypes.c_int), ("height", ctypes.c_int)]
    _fields_ += [("_rest", ctypes.c_byte * 256)]


def grab():
    """Return (width, height, RGB bytes) of the root window."""
    x11 = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
    x11.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong] + [ctypes.c_int] * 2
    x11.XGetImage.argtypes += [ctypes.c_uint] * 2 + [ctypes.c_ulong, ctypes.c_int]
    x11.XGetImage.restype = ctypes.POINTER(XImage)
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("cannot open the X display ($DISPLAY)")
    try:
        root = x11.XDefaultRootWindow(display)
        attrs = XWindowAttributes()
        x11.XGetWindowAttributes(display, root, ctypes.byref(attrs))
        width, height = attrs.width, attrs.height
        image = x11.XGetImage(display, root, 0, 0, width, height, ALL_PLANES, ZPIXMAP).contents
        if image.bits_per_pixel != 32:
            raise RuntimeError(f"unsupported depth: {image.bits_per_pixel} bits per pixel")
        stride = image.bytes_per_line
        raw = ctypes.string_at(image.data, stride * height)
    finally:
        x11.XCloseDisplay(display)
    rgb = bytearray()
    for y in range(height):
        row = raw[y * stride : y * stride + width * 4]
        rgb += interleave(row, width)
    return width, height, bytes(rgb)


def interleave(row, width):
    """BGRX pixels → RGB."""
    out = bytearray(width * 3)
    out[0::3] = row[2::4]
    out[1::3] = row[1::4]
    out[2::3] = row[0::4]
    return out


def png(width, height, rgb):
    def chunk(kind, data):
        body = kind + data
        return struct.pack("!I", len(data)) + body + struct.pack("!I", zlib.crc32(body))

    stride = width * 3
    scanlines = b"".join(b"\0" + rgb[y * stride : (y + 1) * stride] for y in range(height))
    header = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(scanlines, 9))
        + chunk(b"IEND", b"")
    )


def save(path):
    with open(path, "wb") as out:
        out.write(png(*grab()))


if __name__ == "__main__":
    save(sys.argv[1])
