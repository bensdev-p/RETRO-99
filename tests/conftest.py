import os

# Never open a real window or audio device from tests.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pytest

from retro99.render.font import CP437, BitmapFont


@pytest.fixture
def tiny_font() -> BitmapFont:
    """An 8x16 font where every CP437 glyph is a solid top row (cheap, deterministic)."""
    return BitmapFont(8, 16, {ch: (0xFF,) + (0,) * 15 for ch in CP437})
