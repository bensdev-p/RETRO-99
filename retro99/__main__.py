"""Entry point: ``python -m retro99`` or the ``retro99`` console script."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from retro99.config import Config, load_config, set_data_root


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="retro99", description="RETRO-99 game launcher")
    p.add_argument("--config", type=Path, help="path to config.toml")
    p.add_argument(
        "--windowed",
        action="store_true",
        help="development mode: windowed, logs to ./logs (same as RETRO99_DEV=1)",
    )
    p.add_argument("--data-root", type=Path, help="use this folder for games, media and the DB")
    p.add_argument("--scale", type=int, help="window scale factor in windowed mode")
    p.add_argument("--crt", action="store_true", help="enable CRT scanlines")
    p.add_argument(
        "--headless", action="store_true", help="use SDL's dummy video driver (tests / CI)"
    )
    p.add_argument("--frames", type=int, help="exit after rendering this many frames")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p.parse_args(argv)


def setup_logging(config: Config, verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        config.paths.log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(config.paths.log_dir / "retro99.log"))
    except OSError as e:
        print(f"retro99: cannot write logs to {config.paths.log_dir}: {e}", file=sys.stderr)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dev = args.windowed or os.environ.get("RETRO99_DEV") == "1"
    config = load_config(args.config, dev=dev)
    if args.data_root:
        set_data_root(config, args.data_root)
    if args.scale:
        config.display.window_scale = args.scale
    if args.crt:
        config.ui.crt = True
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        config.display.fullscreen = False
    setup_logging(config, args.verbose)
    logging.getLogger(__name__).info("config: %s", config.source or "built-in defaults")

    # Imported late so --help works without initializing pygame.
    from retro99.app import App
    from retro99.screens.library import LibraryScreen

    return App(config).run(LibraryScreen(), max_frames=args.frames)


if __name__ == "__main__":
    sys.exit(main())
