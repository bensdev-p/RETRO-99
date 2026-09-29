"""The 16-color CGA/EGA palette. The only colors the launcher ever draws with."""

from __future__ import annotations

from enum import IntEnum


class Color(IntEnum):
    BLACK = 0
    BLUE = 1
    GREEN = 2
    CYAN = 3
    RED = 4
    MAGENTA = 5
    BROWN = 6
    LIGHT_GRAY = 7
    DARK_GRAY = 8
    LIGHT_BLUE = 9
    LIGHT_GREEN = 10
    LIGHT_CYAN = 11
    LIGHT_RED = 12
    LIGHT_MAGENTA = 13
    YELLOW = 14
    WHITE = 15


# Canonical IBM CGA/EGA RGB values (brown is the "dark yellow" with halved green).
PALETTE: tuple[tuple[int, int, int], ...] = (
    (0x00, 0x00, 0x00),
    (0x00, 0x00, 0xAA),
    (0x00, 0xAA, 0x00),
    (0x00, 0xAA, 0xAA),
    (0xAA, 0x00, 0x00),
    (0xAA, 0x00, 0xAA),
    (0xAA, 0x55, 0x00),
    (0xAA, 0xAA, 0xAA),
    (0x55, 0x55, 0x55),
    (0x55, 0x55, 0xFF),
    (0x55, 0xFF, 0x55),
    (0x55, 0xFF, 0xFF),
    (0xFF, 0x55, 0x55),
    (0xFF, 0x55, 0xFF),
    (0xFF, 0xFF, 0x55),
    (0xFF, 0xFF, 0xFF),
)


def rgb(color: int) -> tuple[int, int, int]:
    """Return the RGB triple for a palette index."""
    return PALETTE[color]


def display_name(color: int) -> str:
    """Human-readable name, e.g. ``Light Cyan``."""
    return Color(color).name.replace("_", " ").title()


def nearest(r: float, g: float, b: float) -> int:
    """Palette index closest to an RGB color (squared Euclidean distance)."""
    best, best_d = 0, float("inf")
    for i, (pr, pg, pb) in enumerate(PALETTE):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best, best_d = i, d
    return best


def dither(rgb_bytes: bytes, width: int, height: int) -> bytearray:
    """Floyd-Steinberg dither packed RGB pixels to palette indices (one byte per pixel)."""
    out = bytearray(width * height)
    cur = [[float(c) for c in rgb_bytes[i * 3 : i * 3 + 3]] for i in range(width)]
    for y in range(height):
        if y + 1 < height:
            base = (y + 1) * width * 3
            nxt = [
                [float(c) for c in rgb_bytes[base + i * 3 : base + i * 3 + 3]] for i in range(width)
            ]
        else:
            nxt = [[0.0, 0.0, 0.0] for _ in range(width)]
        for x in range(width):
            r, g, b = (min(max(c, 0.0), 255.0) for c in cur[x])
            index = nearest(r, g, b)
            out[y * width + x] = index
            pr, pg, pb = PALETTE[index]
            err = (r - pr, g - pg, b - pb)
            for dx, dy, weight in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                nx = x + dx
                if 0 <= nx < width:
                    row = cur if dy == 0 else nxt
                    px = row[nx]
                    px[0] += err[0] * weight
                    px[1] += err[1] * weight
                    px[2] += err[2] * weight
        cur = nxt
    return out


def indices_to_rgb(indices: bytes) -> bytes:
    return b"".join(bytes(PALETTE[i]) for i in indices)
