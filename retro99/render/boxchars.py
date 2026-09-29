"""Procedural CP437 box-drawing and block glyphs in IBM VGA 8x16 geometry.

Used to fill gaps in whatever font is loaded (and to replace the tofu boxes of
the pygame fallback font), so borders always look right.

Each box character is described by its four arms (up, down, left, right) with
weight 0, 1 (single) or 2 (double). Single lines are 2 px wide vertically
(columns 3-4) and 1 px tall horizontally (row 7); double lines use columns
2-3 and 5-6, and rows 5 and 7. Where lines meet, each track stops at a track
of the perpendicular line: inner tracks meet inner tracks and outer meets outer
at corners, a branch stops at the nearest track of a through-line, and a double
through-line is broken where a double branch joins it.
"""

from __future__ import annotations

WIDTH, HEIGHT = 8, 16

# (up, down, left, right)
_ARMS: dict[str, tuple[int, int, int, int]] = {
    "│": (1, 1, 0, 0), "─": (0, 0, 1, 1), "║": (2, 2, 0, 0), "═": (0, 0, 2, 2),
    "┌": (0, 1, 0, 1), "┐": (0, 1, 1, 0), "└": (1, 0, 0, 1), "┘": (1, 0, 1, 0),
    "├": (1, 1, 0, 1), "┤": (1, 1, 1, 0), "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1),
    "╔": (0, 2, 0, 2), "╗": (0, 2, 2, 0), "╚": (2, 0, 0, 2), "╝": (2, 0, 2, 0),
    "╠": (2, 2, 0, 2), "╣": (2, 2, 2, 0), "╦": (0, 2, 2, 2), "╩": (2, 0, 2, 2),
    "╬": (2, 2, 2, 2),
    "╒": (0, 1, 0, 2), "╕": (0, 1, 2, 0), "╘": (1, 0, 0, 2), "╛": (1, 0, 2, 0),
    "╓": (0, 2, 0, 1), "╖": (0, 2, 1, 0), "╙": (2, 0, 0, 1), "╜": (2, 0, 1, 0),
    "╞": (1, 1, 0, 2), "╡": (1, 1, 2, 0), "╤": (0, 1, 2, 2), "╧": (1, 0, 2, 2),
    "╟": (2, 2, 0, 1), "╢": (2, 2, 1, 0), "╥": (0, 2, 1, 1), "╨": (2, 0, 1, 1),
    "╪": (1, 1, 2, 2), "╫": (2, 2, 1, 1),
}  # fmt: skip

# Tracks: vertical lines are column spans, horizontal lines are rows.
_VTRACKS = {1: [(3, 4)], 2: [(2, 3), (5, 6)]}
_HTRACKS = {1: [7], 2: [5, 7]}
_CENTER_ROW, _CENTER_COL = 7, 3


def _vertical_stops(
    up: bool, arm: int, opposite: int, left: int, right: int
) -> list[tuple[tuple[int, int], int]]:
    """For a vertical arm (up if ``up`` else down): (column span, stop row) per track."""
    htracks = sorted(set(_HTRACKS.get(left, []) + _HTRACKS.get(right, [])))
    nearest = (min if up else max)(htracks) if htracks else _CENTER_ROW
    farthest = (max if up else min)(htracks) if htracks else _CENTER_ROW
    out = []
    for i, span in enumerate(_VTRACKS[arm]):
        side = (left, right)[i] if arm == 2 else 0  # perpendicular arm on this track's side
        if not htracks:
            stop = _CENTER_ROW
        elif opposite == arm:  # part of a through-line
            stop = nearest if (arm == 2 and side == 2) else _CENTER_ROW
        elif left and right:  # branch off a through-line
            stop = nearest
        elif arm == 1:  # corner, single
            stop = farthest
        else:  # corner, double: inner track meets inner, outer meets outer
            stop = nearest if side else farthest
        out.append((span, stop))
    return out


def _horizontal_stops(
    left: bool, arm: int, opposite: int, up: int, down: int
) -> list[tuple[int, int]]:
    """For a horizontal arm (left if ``left`` else right): (row, stop column) per track."""
    vspans = sorted(set(_VTRACKS.get(up, []) + _VTRACKS.get(down, [])))
    if vspans:
        near_span = vspans[0] if left else vspans[-1]
        far_span = vspans[-1] if left else vspans[0]
        nearest = near_span[1] if left else near_span[0]
        farthest = far_span[1] if left else far_span[0]
    else:
        nearest = farthest = _CENTER_COL
    out = []
    for i, row in enumerate(_HTRACKS[arm]):
        side = (up, down)[i] if arm == 2 else 0
        if not vspans:
            stop = _CENTER_COL
        elif opposite == arm:
            stop = nearest if (arm == 2 and side == 2) else _CENTER_COL
        elif up and down:
            stop = nearest
        elif arm == 1:
            stop = farthest
        else:
            stop = nearest if side else farthest
        out.append((row, stop))
    return out


def box_glyph(ch: str) -> tuple[int, ...] | None:
    arms = _ARMS.get(ch)
    if arms is None:
        return None
    up, down, left, right = arms
    grid = [[False] * WIDTH for _ in range(HEIGHT)]
    if up:
        for (c0, c1), stop in _vertical_stops(True, up, down, left, right):
            for y in range(0, stop + 1):
                for x in range(c0, c1 + 1):
                    grid[y][x] = True
    if down:
        for (c0, c1), stop in _vertical_stops(False, down, up, left, right):
            for y in range(stop, HEIGHT):
                for x in range(c0, c1 + 1):
                    grid[y][x] = True
    if left:
        for row, stop in _horizontal_stops(True, left, right, up, down):
            for x in range(0, stop + 1):
                grid[row][x] = True
    if right:
        for row, stop in _horizontal_stops(False, right, left, up, down):
            for x in range(stop, WIDTH):
                grid[row][x] = True
    return tuple(sum(1 << (WIDTH - 1 - x) for x in range(WIDTH) if r[x]) for r in grid)


_BLOCKS: dict[str, tuple[int, ...]] = {
    "░": (0x11, 0x44) * 8,
    "▒": (0x55, 0xAA) * 8,
    "▓": (0xDD, 0x77) * 8,
    "█": (0xFF,) * 16,
    "▄": (0x00,) * 7 + (0xFF,) * 9,
    "▀": (0xFF,) * 7 + (0x00,) * 9,
    "▌": (0xF0,) * 16,
    "▐": (0x0F,) * 16,
    "■": (0x00,) * 4 + (0x7C,) * 7 + (0x00,) * 5,
}


def synthesized_glyphs() -> dict[str, tuple[int, ...]]:
    """All glyphs this module can draw, keyed by character."""
    glyphs = {ch: rows for ch in _ARMS if (rows := box_glyph(ch)) is not None}
    glyphs.update(_BLOCKS)
    return glyphs
