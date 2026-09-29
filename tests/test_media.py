import pygame

from retro99.library.media import ega_art_path, find_art, fit_size, load_ega_art
from retro99.render.palette import PALETTE, dither, nearest


def test_nearest_palette_color():
    assert nearest(0, 0, 0) == 0
    assert nearest(250, 250, 250) == 15
    assert nearest(0, 0, 160) == 1


def test_dither_exact_palette_colors_are_unchanged():
    pixels = bytes(PALETTE[4]) * 4 + bytes(PALETTE[14]) * 4
    assert list(dither(pixels, 4, 2)) == [4] * 4 + [14] * 4


def test_dither_mid_gray_mixes_colors():
    out = dither(bytes([128, 128, 128]) * 64, 8, 8)
    assert len(set(out)) > 1  # error diffusion, not a flat nearest-color fill
    mean = sum(PALETTE[i][0] for i in out) / len(out)
    assert abs(mean - 128) < 20


def test_fit_size():
    assert fit_size((300, 400), (144, 112)) == (84, 112)
    assert fit_size((400, 100), (144, 112)) == (144, 36)


def test_art_is_dithered_and_cached(tmp_path):
    media = tmp_path / "media"
    (media / "duke3d").mkdir(parents=True)
    src = pygame.Surface((30, 40))
    src.fill((200, 120, 40))
    pygame.image.save(src, str(media / "duke3d" / "cover.png"))
    assert find_art(media, "duke3d") == media / "duke3d" / "cover.png"
    art = load_ega_art(media, "duke3d", (144, 112))
    assert art.get_size() == (84, 112)
    dst = ega_art_path(media, "duke3d", (144, 112))
    assert dst.is_file()
    colors = {tuple(art.get_at((x, y)))[:3] for x in range(0, 84, 7) for y in range(0, 112, 7)}
    assert colors <= set(PALETTE)
    mtime = dst.stat().st_mtime_ns
    load_ega_art(media, "duke3d", (144, 112))
    assert dst.stat().st_mtime_ns == mtime  # reused, not regenerated


def test_no_art_and_broken_art(tmp_path):
    assert load_ega_art(tmp_path, "nothing", (10, 10)) is None
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "cover.png").write_bytes(b"not a png")
    assert load_ega_art(tmp_path, "bad", (10, 10)) is None
