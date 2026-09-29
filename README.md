# RETRO-99

A fullscreen, early-90s-DOS-style game launcher for a Raspberry Pi 5 in a gutted
TI-99/4A case. See [CLAUDE.md](CLAUDE.md) for the full design and the phased plan.

**Status:** Phase 1 (renderer) is done. It includes the 80×25 text grid, the CGA/EGA palette, VGA
font loading, and the widgets: windows, lists, menus, dialogs, text input, and the function-key bar.
A demo screen shows the three-pane layout with placeholder data.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
RETRO99_DEV=1 .venv/bin/python -m retro99      # or: python -m retro99 --windowed
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The VGA font (PxPlus IBM VGA 8x16, CC BY-SA 4.0) is bundled; see
[assets/fonts/README.md](assets/fonts/README.md) for attribution and fallbacks.

Useful flags: `--scale N` (window scale), `--crt` (scanlines), `--headless --frames N`
(render with SDL's dummy driver and exit), `--config PATH`, `-v`.

Keys in the demo: arrows/Tab to move between panes, Enter to open, Esc or F10 for the menu,
letters to jump, F1 help, F2 favorite, F3 info, Alt-X quit. Options → *Palette and font test*
shows all 16 colors and the full CP437 chart.
