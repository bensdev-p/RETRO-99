# Fonts

RETRO-99 draws everything with an 8×16 VGA bitmap font. It tries the fonts in
`[paths].fonts` of `config.toml` in order:

1. **`Px437_IBM_VGA_8x16.ttf`** (recommended). This file is from *The Ultimate Oldschool PC Font Pack* by
   VileR (<https://int10h.org/oldschool-pc-fonts/>), licensed CC BY-SA 4.0.
   Download the pack and copy `Px437_IBM_VGA_8x16.ttf` into this folder.
   It is not committed yet.
2. **`/usr/share/consolefonts/default8x16.psf.gz`** is the VGA ROM font from
   Debian's `console-data` package (`sudo apt install console-data`). It has
   full CP437 coverage.
3. **`/usr/share/consolefonts/Uni2-VGA16.psf.gz`** comes with Raspberry Pi OS by
   default. It is missing a few CP437 glyphs (e.g. `►`, `▀▄▌▐`) and draws double
   box lines as single ones.
4. If none of these are found, RETRO-99 falls back to a crude font built from
   pygame's default typeface, so the app still starts.

Whichever font loads, any missing box-drawing or block characters (`╔═╗ ▀▄▌▐ ░▒▓`)
are filled in with glyphs generated in `retro99/render/boxchars.py`. These match the
VGA ROM pixel for pixel.
