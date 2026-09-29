"""Box art: find it under ``media/<game-id>/`` and cache an EGA-dithered copy there.

Dithering is slow in pure Python, so ``make_ega_art`` is meant for a worker
thread; the result is cached as a PNG and reused until the source changes.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from retro99.render.palette import dither, indices_to_rgb

log = logging.getLogger(__name__)

ART_NAMES = ("cover", "boxart", "box", "front")
ART_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")


def find_art(media_dir: Path, game_id: str) -> Path | None:
    folder = media_dir / game_id
    for name in ART_NAMES:
        for ext in ART_EXTENSIONS:
            candidate = folder / f"{name}{ext}"
            if candidate.is_file():
                return candidate
    return None


def ega_art_path(media_dir: Path, game_id: str, size: tuple[int, int]) -> Path:
    return media_dir / game_id / f"art_ega_{size[0]}x{size[1]}.png"


def fit_size(src: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """Largest size with ``src``'s aspect ratio that fits in ``box``."""
    sw, sh = src
    bw, bh = box
    scale = min(bw / sw, bh / sh)
    return max(1, round(sw * scale)), max(1, round(sh * scale))


def make_ega_art(src: Path, dst: Path, box: tuple[int, int]) -> Path:
    """Scale ``src`` to fit ``box``, dither to the 16-color palette, save to ``dst``."""
    image = pygame.image.load(str(src))
    size = fit_size(image.get_size(), box)
    # Flatten to 24-bit RGB (paletted/alpha images) without needing a display.
    flat = pygame.Surface(image.get_size(), depth=24)
    flat.blit(image, (0, 0))
    scaled = pygame.transform.smoothscale(flat, size)
    rgb = pygame.image.tobytes(scaled, "RGB")
    indices = dither(rgb, *size)
    out = pygame.image.frombytes(indices_to_rgb(indices), size, "RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(out, str(dst))
    return dst


def load_ega_art(media_dir: Path, game_id: str, box: tuple[int, int]) -> pygame.Surface | None:
    """The cached dithered art for a game, generating it if needed. Worker-thread safe
    (touches no display). Returns None when the game has no art."""
    src = find_art(media_dir, game_id)
    if src is None:
        return None
    dst = ega_art_path(media_dir, game_id, box)
    try:
        if not dst.is_file() or dst.stat().st_mtime < src.stat().st_mtime:
            make_ega_art(src, dst, box)
        return pygame.image.load(str(dst))
    except (pygame.error, OSError) as e:
        log.warning("box art for %s failed: %s", game_id, e)
        return None
