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
