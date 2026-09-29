import gzip
import struct

import pytest

from retro99.render.font import CP437, BitmapFont, fallback_font, load_font, parse_psf


def psf1(glyphs: list[bytes], table: list[list[int]] | None = None, height: int = 16) -> bytes:
    count = 512 if len(glyphs) > 256 else 256
    glyphs = glyphs + [bytes(height)] * (count - len(glyphs))
    mode = (0x01 if count == 512 else 0) | (0x02 if table is not None else 0)
    data = b"\x36\x04" + bytes([mode, height]) + b"".join(glyphs)
    if table is not None:
        table = table + [[]] * (count - len(table))
        for codes in table:
            data += b"".join(struct.pack("<H", c) for c in codes) + b"\xff\xff"
    return data


def psf2(width: int, height: int, glyphs: list[bytes], table: list[str] | None) -> bytes:
    stride = (width + 7) // 8
    charsize = stride * height
    flags = 1 if table is not None else 0
    header = struct.pack(
        "<4sIIIIIII", b"\x72\xb5\x4a\x86", 0, 32, flags, len(glyphs), charsize, height, width
    )
    data = header + b"".join(glyphs)
    if table is not None:
        for chars in table:
            data += chars.encode() + b"\xff"
    return data


def test_psf1_without_table_uses_cp437_order():
    a_glyph = bytes([0x18] * 16)
    glyphs = [bytes(16)] * 0x41 + [a_glyph]  # index 0x41 = 'A'
    font = parse_psf(psf1(glyphs))
    assert (font.width, font.height) == (8, 16)
    assert font.rows("A") == tuple([0x18] * 16)
    assert font.has("╔")  # every CP437 slot is mapped


def test_psf1_unicode_table_maps_multiple_codepoints():
    box = bytes([0xFF] + [0] * 15)
    font = parse_psf(psf1([box], table=[[ord("─"), ord("━")]]))
    assert font.rows("─") == font.rows("━") == tuple(box)


def test_psf1_sequences_are_ignored():
    g = bytes([1] * 16)
    font = parse_psf(psf1([g], table=[[ord("e"), 0xFFFE, ord("e"), 0x0301]]))
    assert font.has("e")
    assert not font.has("́")


def test_psf2_wide_glyph_rows_and_gzip():
    # 10 px wide -> 2 bytes per row; set leftmost and rightmost pixels.
    row = (0b1000000001 << 6).to_bytes(2, "big")
    data = psf2(10, 4, [row * 4], ["X"])
    font = parse_psf(gzip.compress(data))
    assert (font.width, font.height) == (10, 4)
    assert font.rows("X") == (0b1000000001,) * 4


def test_bad_magic_raises():
    with pytest.raises(ValueError):
        parse_psf(b"not a font")


def test_missing_glyph_substitutes_then_question_mark():
    q = (1,) * 16
    gt = (2,) * 16
    font = BitmapFont(8, 16, {"?": q, ">": gt})
    assert font.rows("►") == gt
    assert font.rows("☺") == q
    assert font.rows(" ") == (0,) * 16
    assert font.missing("►? ") == ["►"]


def test_load_font_skips_missing_and_broken(tmp_path):
    broken = tmp_path / "broken.psf"
    broken.write_bytes(b"garbage")
    good = tmp_path / "good.psf"
    good.write_bytes(psf1([bytes(16)] * 256))
    font = load_font([tmp_path / "nope.ttf", broken, good])
    assert font.name == "good.psf"


def test_fallback_font_covers_ascii():
    font = load_font([])
    assert (font.width, font.height) == (8, 16)
    assert font.name == fallback_font().name
    assert all(font.has(c) for c in "AZaz09")
    assert len(CP437) == 256


def test_synthesized_box_glyphs_follow_vga_geometry():
    from retro99.render.boxchars import box_glyph, synthesized_glyphs

    def pic(ch):
        return ["".join("#" if r & (0x80 >> x) else "." for x in range(8)) for r in box_glyph(ch)]

    assert pic("─")[7] == "########" and pic("─")[6] == "........"
    assert set(pic("│")) == {"...##..."}
    assert pic("╔")[4:9] == ["........", "..######", "..##....", "..##.###", "..##.##."]
    assert pic("╬")[5:8] == ["####.###", "........", "####.###"]
    assert pic("╧")[4:8] == ["...##...", "########", "........", "########"]
    assert pic("╜")[7] == "#######."
    assert box_glyph("A") is None
    assert all(len(rows) == 16 for rows in synthesized_glyphs().values())


def test_add_box_glyphs_fills_gaps_only_for_8x16():
    font = BitmapFont(8, 16, {"─": (1,) * 16})
    added = font.add_box_glyphs()
    assert font.rows("─") == (1,) * 16  # existing glyphs kept
    assert font.has("╔") and font.has("▀") and added > 40
    assert BitmapFont(8, 8, {}).add_box_glyphs() == 0


def test_fallback_font_has_real_box_drawing():
    from retro99.render.boxchars import box_glyph

    assert fallback_font().rows("╔") == box_glyph("╔")


def test_bundled_vga_font_is_pixel_exact_8x16():
    from retro99.config import DEFAULT_FONTS, resolve_path

    font = load_font([resolve_path(DEFAULT_FONTS[0])])
    assert font.name == "PxPlus_IBM_VGA_8x16.ttf"
    assert (font.width, font.height) == (8, 16)
    assert font.missing(CP437) == []
    # Double-line corner straight from the VGA ROM.
    assert font.rows("╔")[5:8] == (0b00111111, 0b00110000, 0b00110111)
