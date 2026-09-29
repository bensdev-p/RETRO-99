# RETRO-99

A fullscreen, early-90s-DOS-style game launcher for a Raspberry Pi 5 in a gutted
TI-99/4A case. See [CLAUDE.md](CLAUDE.md) for the full design and the phased plan.

**Status:** Phases 1 and 2 are done.

- **Phase 1 (renderer):** the 80×25 text grid, the CGA/EGA palette, the VGA font, and the widgets:
  windows, lists, menus, dialogs, text input, and the function-key bar.
- **Phase 2 (library):** `game.toml` validation, the systems table (defaults can be overridden
  in `config.toml`), the scanner for bundles and ROMs, the SQLite index, and the three-pane
  library screen with real data. That includes favorites and recent filters, red `[!]` markers
  for broken manifests, and box art dithered to the EGA palette.

Launching games comes in Phase 3.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
RETRO99_DEV=1 .venv/bin/python -m retro99      # or: python -m retro99 --windowed
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

To try the library with sample data, copy the test fixtures (the UI writes favorites into
`game.toml`) and point the app at them:

```sh
cp -r tests/fixtures/library /tmp/retro99-sample
RETRO99_DEV=1 .venv/bin/python -m retro99 --data-root /tmp/retro99-sample
```

Box art is read from `media/<game-id>/cover.png` (or `boxart`/`box`/`front`, as png/jpg/gif/bmp).
The EGA-dithered copy is cached next to it.

The VGA font (PxPlus IBM VGA 8x16, CC BY-SA 4.0) is bundled; see
[assets/fonts/README.md](assets/fonts/README.md) for attribution and fallbacks.

Useful flags: `--scale N` (window scale), `--crt` (scanlines), `--headless --frames N`
(render with SDL's dummy driver and exit), `--data-root DIR`, `--config PATH`, `-v`.

Keys: arrows/Tab to move between panes, Enter to open, Esc or F10 for the menu,
letters to jump, F1 help, F2 favorite, F3 info, F5 rescan, Alt-X quit. Options → *Palette and font test*
shows all 16 colors and the full CP437 chart.
