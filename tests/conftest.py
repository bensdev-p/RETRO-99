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


FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


@pytest.fixture
def library_root(tmp_path):
    """A writable copy of tests/fixtures/library (scans may rewrite game.toml)."""
    import shutil

    root = tmp_path / "library"
    shutil.copytree(FIXTURES / "library", root)
    return root


@pytest.fixture
def library_config(library_root):
    from retro99.config import parse_config, set_data_root

    cfg = parse_config({}, dev=True)
    set_data_root(cfg, library_root)
    cfg.library.scan_on_start = False
    return cfg
