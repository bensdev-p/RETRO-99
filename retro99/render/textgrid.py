"""The 80x25 character-cell grid and the renderer that turns it into pixels.

``TextGrid`` is pure data (a character plus foreground/background palette
index per cell) so screens and widgets can be tested without a display.
``GridRenderer`` rasterizes it with a ``BitmapFont``, redrawing only the cells
that changed since the previous frame.
"""

from __future__ import annotations

from collections.abc import Iterator

import pygame

from retro99.render.font import BitmapFont
from retro99.render.palette import Color, rgb

COLS = 80
ROWS = 25


class TextGrid:
    def __init__(self, cols: int = COLS, rows: int = ROWS) -> None:
        self.cols = cols
        self.rows = rows
        size = cols * rows
        self.chars: list[str] = [" "] * size
        self.fg: list[int] = [Color.LIGHT_GRAY] * size
        self.bg: list[int] = [Color.BLACK] * size
        # Position of the blinking block cursor, or None when nothing is editable.
        self.cursor: tuple[int, int] | None = None

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def clear(self, fg: int = Color.LIGHT_GRAY, bg: int = Color.BLACK) -> None:
        size = self.cols * self.rows
        self.chars[:] = [" "] * size
        self.fg[:] = [fg] * size
        self.bg[:] = [bg] * size
        self.cursor = None

    def put(self, x: int, y: int, ch: str, fg: int | None = None, bg: int | None = None) -> None:
        """Set one cell. ``None`` colors keep the cell's current color."""
        if not self.in_bounds(x, y):
            return
        i = y * self.cols + x
        self.chars[i] = ch
        if fg is not None:
            self.fg[i] = fg
        if bg is not None:
            self.bg[i] = bg

    def write(
        self,
        x: int,
        y: int,
        text: str,
        fg: int | None = None,
        bg: int | None = None,
        width: int | None = None,
    ) -> int:
        """Write ``text`` left to right, clipped to ``width`` and the grid edge.

        Returns the number of cells written.
        """
        if width is not None:
            text = text[: max(width, 0)]
        written = 0
        for offset, ch in enumerate(text):
            if x + offset >= self.cols:
                break
            self.put(x + offset, y, ch, fg, bg)
            written += 1
        return written

    def fill(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        ch: str = " ",
        fg: int | None = None,
        bg: int | None = None,
    ) -> None:
        for cy in range(y, y + h):
            for cx in range(x, x + w):
                self.put(cx, cy, ch, fg, bg)

    def recolor(
        self, x: int, y: int, w: int, h: int, fg: int | None = None, bg: int | None = None
    ) -> None:
        """Change colors in a rectangle, keeping the characters."""
        for cy in range(y, y + h):
            for cx in range(x, x + w):
                if self.in_bounds(cx, cy):
                    i = cy * self.cols + cx
                    if fg is not None:
                        self.fg[i] = fg
                    if bg is not None:
                        self.bg[i] = bg

    def cell(self, x: int, y: int) -> tuple[str, int, int]:
        i = y * self.cols + x
        return self.chars[i], self.fg[i], self.bg[i]

    def row_text(self, y: int) -> str:
        start = y * self.cols
        return "".join(self.chars[start : start + self.cols])

    def text(self) -> str:
        """The whole grid as plain text, one line per row (handy in tests)."""
        return "\n".join(self.row_text(y) for y in range(self.rows))

    def cells(self) -> Iterator[tuple[int, int, str, int, int]]:
        for i, ch in enumerate(self.chars):
            yield i % self.cols, i // self.cols, ch, self.fg[i], self.bg[i]


class GridRenderer:
    """Rasterizes a TextGrid onto a native-resolution surface (640x400 for 8x16)."""

    def __init__(self, font: BitmapFont, cols: int = COLS, rows: int = ROWS) -> None:
        self.font = font
        self.cols = cols
        self.rows = rows
        self.surface = pygame.Surface((cols * font.width, rows * font.height))
        self._cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._prev: list[tuple[str, int, int] | None] = [None] * (cols * rows)

    @property
    def size(self) -> tuple[int, int]:
        return self.surface.get_size()

    def invalidate(self) -> None:
        """Force a full redraw on the next frame (e.g. after the display is re-created)."""
        self._prev = [None] * (self.cols * self.rows)

    def _cell_surface(self, ch: str, fg: int, bg: int) -> pygame.Surface:
        key = (ch, fg, bg)
        surf = self._cache.get(key)
        if surf is None:
            w, h = self.font.width, self.font.height
            surf = pygame.Surface((w, h))
            surf.fill(rgb(bg))
            color = rgb(fg)
            top_bit = 1 << (w - 1)
            for y, bits in enumerate(self.font.rows(ch)):
                if not bits:
                    continue
                for x in range(w):
                    if bits & (top_bit >> x):
                        surf.set_at((x, y), color)
            self._cache[key] = surf
        return surf

    def render(self, grid: TextGrid, cursor_on: bool = True) -> pygame.Surface:
        w, h = self.font.width, self.font.height
        cursor_index = -1
        if grid.cursor is not None and cursor_on and grid.in_bounds(*grid.cursor):
            cx, cy = grid.cursor
            cursor_index = cy * grid.cols + cx
        prev = self._prev
        chars, fgs, bgs = grid.chars, grid.fg, grid.bg
        blit = self.surface.blit
        for i in range(self.cols * self.rows):
            fg, bg = fgs[i], bgs[i]
            if i == cursor_index:
                fg, bg = bg, fg  # block cursor: invert the cell
            state = (chars[i], fg, bg)
            if prev[i] != state:
                prev[i] = state
                blit(self._cell_surface(*state), ((i % self.cols) * w, (i // self.cols) * h))
        return self.surface
