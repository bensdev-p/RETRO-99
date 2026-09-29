# Fonts

RETRO-99 draws everything with an 8×16 VGA bitmap font. It tries the fonts in
`[paths].fonts` of `config.toml` in order:

1. **`PxPlus_IBM_VGA_8x16.ttf`** is bundled here. It comes from *The Ultimate
   Oldschool PC Font Pack* by VileR (<https://int10h.org/oldschool-pc-fonts/>),
   licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). It
   has the IBM VGA ROM glyphs with full CP437 coverage, and it rasterizes
   pixel-exact at 16 px.
2. **`Px437_IBM_VGA_8x16.ttf`**: the same font from the same pack, limited to
   CP437. Either one works.
3. **`/usr/share/consolefonts/default8x16.psf.gz`**: a VGA font from Debian's
   `console-data` package.
4. **`/usr/share/consolefonts/Uni2-VGA16.psf.gz`** comes with Raspberry Pi OS by
   default. It is missing a few CP437 glyphs and draws double box lines as
   single ones.
5. If none of these are found, RETRO-99 falls back to a crude font built from
   pygame's default typeface, so the app still starts.

Whichever font loads, any missing box-drawing or block characters (`╔═╗ ▀▄▌▐ ░▒▓`)
are filled in with glyphs generated in `retro99/render/boxchars.py`. These match the
VGA ROM pixel for pixel.
