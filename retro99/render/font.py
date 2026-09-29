"""Bitmap fonts for the character grid.

Glyphs are stored as rows of bits (bit ``width - 1`` is the leftmost pixel), so
parsing and lookup are pure logic that never touches a display. Three sources
are supported, tried in the order given by ``config.toml``:

* a TrueType bitmap font such as PxPlus/Px437 IBM VGA 8x16 (rasterized once at load),
* a Linux console PSF font (PSF1/PSF2, optionally gzipped), e.g. the
  ``Uni2-VGA16.psf.gz`` that ships with Raspberry Pi OS,
* a last-resort fallback built from pygame's default font so the app still
  starts on a machine with neither.
"""

from __future__ import annotations

import gzip
import logging
import struct
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Code page 437 as Unicode, indexed by byte value. 0x00-0x1F and 0x7F use the
# glyphs the VGA ROM shows for them rather than control codes.
CP437: str = (
    "\x00☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
    + bytes(range(0x20, 0x7F)).decode("ascii")
    + "⌂"
    + bytes(range(0x80, 0x100)).decode("cp437")
)

# Look-alikes used when a font lacks a glyph.
SUBSTITUTES: dict[str, str] = {
    "►": ">",
    "◄": "<",
    "▲": "^",
    "▼": "v",
    "↑": "^",
    "↓": "v",
    "→": ">",
    "←": "<",
    "■": "#",
    "░": "#",
    "▒": "#",
    "▓": "#",
    "♥": "*",
    "√": "v",
    "…": ".",
    " ": " ",
}

_PSF1_MAGIC = b"\x36\x04"
_PSF2_MAGIC = b"\x72\xb5\x4a\x86"


@dataclass
class BitmapFont:
    width: int
    height: int
    glyphs: dict[str, tuple[int, ...]]
    name: str = ""
    _blank: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._blank = (0,) * self.height

    def has(self, ch: str) -> bool:
        return ch in self.glyphs

    def rows(self, ch: str) -> tuple[int, ...]:
        """Bitmap rows for ``ch``, falling back to a look-alike, then ``?``."""
        if ch in self.glyphs:
            return self.glyphs[ch]
        if ch == " " or ch == "\x00":
            return self._blank
        sub = SUBSTITUTES.get(ch)
        if sub is not None and sub in self.glyphs:
            return self.glyphs[sub]
        return self.glyphs.get("?", self._blank)

    def missing(self, chars: Iterable[str]) -> list[str]:
        return [c for c in chars if c not in self.glyphs and c not in " \x00"]

    def add_box_glyphs(self, *, replace: bool = False) -> int:
        """Fill in procedural box-drawing/block glyphs (8x16 fonts only).

        Returns how many glyphs were added or replaced.
        """
        if (self.width, self.height) != (8, 16):
            return 0
        from retro99.render.boxchars import synthesized_glyphs

        count = 0
        for ch, rows in synthesized_glyphs().items():
            if replace or ch not in self.glyphs:
                self.glyphs[ch] = rows
                count += 1
        return count


def parse_psf(data: bytes, name: str = "") -> BitmapFont:
    """Parse a PSF1 or PSF2 console font (gzipped or not)."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if data[:2] == _PSF1_MAGIC:
        return _parse_psf1(data, name)
    if data[:4] == _PSF2_MAGIC:
        return _parse_psf2(data, name)
    raise ValueError(f"not a PSF font: {name or '<bytes>'}")


def _parse_psf1(data: bytes, name: str) -> BitmapFont:
    mode, charsize = data[2], data[3]
    count = 512 if mode & 0x01 else 256
    bitmaps = [tuple(data[4 + i * charsize : 4 + (i + 1) * charsize]) for i in range(count)]
    table_start = 4 + count * charsize
    mapping: list[list[str]] | None = None
    if mode & 0x06:
        mapping = _psf1_unicode_table(data[table_start:], count)
    return _build(8, charsize, bitmaps, mapping, name)


def _psf1_unicode_table(table: bytes, count: int) -> list[list[str]]:
    mapping: list[list[str]] = []
    pos = 0
    for _ in range(count):
        chars: list[str] = []
        in_sequence = False
        while pos + 1 < len(table):
            (value,) = struct.unpack_from("<H", table, pos)
            pos += 2
            if value == 0xFFFF:
                break
            if value == 0xFFFE:
                in_sequence = True  # combining sequences are not single cells
            elif not in_sequence:
                chars.append(chr(value))
        mapping.append(chars)
    return mapping


def _parse_psf2(data: bytes, name: str) -> BitmapFont:
    (_magic, _version, headersize, flags, count, charsize, height, width) = struct.unpack_from(
        "<4sIIIIIII", data, 0
    )
    stride = (width + 7) // 8
    bitmaps: list[tuple[int, ...]] = []
    for i in range(count):
        raw = data[headersize + i * charsize : headersize + (i + 1) * charsize]
        rows = []
        for r in range(height):
            value = int.from_bytes(raw[r * stride : (r + 1) * stride], "big")
            rows.append(value >> (stride * 8 - width))
        bitmaps.append(tuple(rows))
    mapping: list[list[str]] | None = None
    if flags & 0x01:
        mapping = _psf2_unicode_table(data[headersize + count * charsize :], count)
    return _build(width, height, bitmaps, mapping, name)


def _psf2_unicode_table(table: bytes, count: int) -> list[list[str]]:
    mapping: list[list[str]] = []
    for entry in table.split(b"\xff")[:count]:
        single = entry.split(b"\xfe", 1)[0]
        mapping.append(list(single.decode("utf-8", errors="ignore")))
    while len(mapping) < count:
        mapping.append([])
    return mapping


def _build(
    width: int,
    height: int,
    bitmaps: Sequence[tuple[int, ...]],
    mapping: list[list[str]] | None,
    name: str,
) -> BitmapFont:
    glyphs: dict[str, tuple[int, ...]] = {}
    if mapping is None:
        # No Unicode table: assume the glyphs are in CP437 order.
        for index, rows in enumerate(bitmaps[: len(CP437)]):
            glyphs[CP437[index]] = rows
    else:
        for rows, chars in zip(bitmaps, mapping, strict=False):
            for ch in chars:
                glyphs.setdefault(ch, rows)
    return BitmapFont(width, height, glyphs, name)


def rasterize_ttf(path: Path, size: int = 16, chars: str = CP437) -> BitmapFont:
    """Rasterize a TrueType bitmap-style font (e.g. PxPlus/Px437) into a BitmapFont."""
    import pygame

    if not pygame.font.get_init():
        pygame.font.init()
    ttf = pygame.font.Font(str(path), size)
    width, height = ttf.size("█")
    return _rasterize(ttf, width, height, chars, path.name, center=False)


def fallback_font(width: int = 8, height: int = 16) -> BitmapFont:
    """Crude font from pygame's built-in typeface; only used when nothing else loads."""
    import pygame

    if not pygame.font.get_init():
        pygame.font.init()
    ttf = pygame.font.Font(None, height)
    font = _rasterize(ttf, width, height, CP437, "pygame-default", center=True)
    font.add_box_glyphs(replace=True)  # the default typeface has no box drawing
    return font


def _rasterize(ttf, width: int, height: int, chars: str, name: str, center: bool) -> BitmapFont:
    import pygame

    glyphs: dict[str, tuple[int, ...]] = {}
    for ch in dict.fromkeys(chars):
        if ch == "\x00" or (ch != " " and not _has_glyph(ttf, ch)):
            continue
        surf = ttf.render(ch, False, (255, 255, 255))
        mask = pygame.mask.from_surface(surf)
        mw, mh = mask.get_size()
        ox = (width - mw) // 2 if center else 0
        oy = (height - mh) // 2 if center else 0
        rows = []
        for y in range(height):
            bits = 0
            sy = y - oy
            for x in range(width):
                sx = x - ox
                bits <<= 1
                if 0 <= sx < mw and 0 <= sy < mh and mask.get_at((sx, sy)):
                    bits |= 1
            rows.append(bits)
        glyphs[ch] = tuple(rows)
    return BitmapFont(width, height, glyphs, name)


def _has_glyph(ttf, ch: str) -> bool:
    try:
        metrics = ttf.metrics(ch)
    except (ValueError, UnicodeError):
        return False
    return bool(metrics) and metrics[0] is not None


def load_font(paths: Iterable[Path]) -> BitmapFont:
    """Load the first usable font from ``paths``; fall back to a built-in one."""
    for path in paths:
        if not path.is_file():
            log.debug("font not found: %s", path)
            continue
        try:
            suffixes = "".join(path.suffixes).lower()
            if ".psf" in suffixes:
                font = parse_psf(path.read_bytes(), path.name)
            elif suffixes.endswith((".ttf", ".otf")):
                font = rasterize_ttf(path)
            else:
                log.warning("unknown font type, skipping: %s", path)
                continue
        except Exception:
            log.exception("failed to load font %s", path)
            continue
        added = font.add_box_glyphs()
        missing = font.missing(CP437)
        if added or missing:
            log.info(
                "font %s: %d box/block glyphs synthesized, %d CP437 glyphs missing",
                path.name,
                added,
                len(missing),
            )
        log.info("using font %s (%dx%d)", path, font.width, font.height)
        return font
    log.warning("no VGA font found; using pygame fallback font")
    return fallback_font()
