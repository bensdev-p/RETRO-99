"""Loading ``config.toml``.

Code defaults are development-friendly (paths relative to the project root);
the Pi's real paths live in ``config.example.toml``, which ``install.sh``
copies into place. Relative paths in the config resolve against the project
root, so ``assets/fonts/...`` works both from a checkout and from /opt/retro99.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_FONTS = [
    "assets/fonts/Px437_IBM_VGA_8x16.ttf",
    # Debian/Raspberry Pi OS package `console-data`: the genuine VGA ROM font.
    "/usr/share/consolefonts/default8x16.psf.gz",
    # Installed by default on Raspberry Pi OS; lacks a few CP437 glyphs.
    "/usr/share/consolefonts/Uni2-VGA16.psf.gz",
]


@dataclass
class DisplayConfig:
    fullscreen: bool = True
    window_scale: int = 2
    fps: int = 30


@dataclass
class UiConfig:
    crt: bool = False
    crt_strength: int = 96


@dataclass
class PathsConfig:
    data_root: Path = Path("data")
    log_dir: Path = Path("logs")
    fonts: list[Path] = field(default_factory=lambda: [Path(p) for p in DEFAULT_FONTS])


@dataclass
class Config:
    dev: bool = False
    source: Path | None = None
    display: DisplayConfig = field(default_factory=DisplayConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    raw: dict[str, Any] = field(default_factory=dict)


def resolve_path(value: str | Path, root: Path = PROJECT_ROOT) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def find_config(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("RETRO99_CONFIG")
    if env:
        return Path(env)
    for candidate in (Path.cwd() / "config.toml", Path("/etc/retro99/config.toml")):
        if candidate.is_file():
            return candidate
    return None


def parse_config(data: dict[str, Any], *, dev: bool, source: Path | None = None) -> Config:
    cfg = Config(dev=dev, source=source, raw=data)

    display = data.get("display", {})
    cfg.display.fullscreen = bool(display.get("fullscreen", cfg.display.fullscreen))
    cfg.display.window_scale = int(display.get("window_scale", cfg.display.window_scale))
    cfg.display.fps = int(display.get("fps", cfg.display.fps))

    ui = data.get("ui", {})
    cfg.ui.crt = bool(ui.get("crt", cfg.ui.crt))
    cfg.ui.crt_strength = int(ui.get("crt_strength", cfg.ui.crt_strength))

    paths = data.get("paths", {})
    cfg.paths.data_root = resolve_path(paths.get("data_root", cfg.paths.data_root))
    cfg.paths.log_dir = resolve_path(paths.get("log_dir", cfg.paths.log_dir))
    fonts = paths.get("fonts", DEFAULT_FONTS)
    cfg.paths.fonts = [resolve_path(p) for p in fonts]

    if dev:
        # Development always runs windowed and logs into the checkout.
        cfg.display.fullscreen = False
        cfg.paths.log_dir = PROJECT_ROOT / "logs"
    return cfg


def load_config(path: Path | None = None, *, dev: bool = False) -> Config:
    source = find_config(path)
    data: dict[str, Any] = {}
    if source is not None:
        with source.open("rb") as f:
            data = tomllib.load(f)
    return parse_config(data, dev=dev, source=source)
