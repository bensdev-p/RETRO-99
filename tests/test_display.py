import pygame

from retro99.render.crt import CrtEffect
from retro99.render.display import Viewport, compute_viewport


def test_integer_scale_with_letterbox_on_1080p():
    assert compute_viewport((1920, 1080), (640, 400)) == Viewport(320, 140, 1280, 800, 2)


def test_integer_scale_on_4k_and_exact_fit():
    assert compute_viewport((3840, 2160), (640, 400)).scale == 5
    assert compute_viewport((640, 400), (640, 400)) == Viewport(0, 0, 640, 400, 1)


def test_small_window_shrinks_keeping_aspect():
    vp = compute_viewport((320, 400), (640, 400))
    assert vp.scale == 0
    assert (vp.w, vp.h) == (320, 200)
    assert vp.y == 100


def test_crt_scanlines_darken_every_other_row_at_2x():
    surf = pygame.Surface((4, 4))
    surf.fill((200, 200, 200))
    CrtEffect(enabled=True, strength=255).apply(surf, 2)
    assert surf.get_at((0, 0))[:3] == (200, 200, 200)
    assert surf.get_at((0, 1))[:3] == (0, 0, 0)


def test_crt_disabled_or_1x_is_noop():
    surf = pygame.Surface((4, 4))
    surf.fill((200, 200, 200))
    CrtEffect(enabled=False).apply(surf, 2)
    CrtEffect(enabled=True).apply(surf, 1)
    assert surf.get_at((0, 1))[:3] == (200, 200, 200)
