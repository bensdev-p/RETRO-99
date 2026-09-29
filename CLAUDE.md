# CLAUDE.md — RETRO-99: DOS-Style Game Launcher for Raspberry Pi 5

## Project Overview

A custom, fullscreen game launcher for a Raspberry Pi 5 housed in a gutted TI-99/4A case. It looks and feels like an early-90s DOS program (Norton Commander / MS-DOS Shell / Turbo Pascal IDE), and it manages and launches:

- **Ripped DOS/PC games** (from CD and floppy), packaged as bundles
- **Native source ports** (EDuke32, Xash3D FWGS) that use original game data
- **Windows 9x games** via Box64 + Wine (e.g. StarCraft)
- **Console ROMs**, both ripped from owned media and uploaded as files (cartridge ROMs, CHD/BIN/CUE disc images)

**The launcher never emulates anything itself.** It is a library manager and launcher. It hands each game to an external program, waits for it to exit, and redraws itself.

## Target Environment

- **Hardware:** Raspberry Pi 5 (8 GB), active cooler, HDMI out, USB gamepad(s) plus a keyboard
- **OS:** Raspberry Pi OS Lite, 64-bit, with no desktop environment
- **Display:** Fullscreen via SDL2's KMS/DRM backend (no X11/Wayland)
- **Boot:** Runs as a systemd service on tty1; boot straight into the launcher
- **Development:** The code must also run windowed on a Linux/macOS/Windows desktop for development. Detect this with `RETRO99_DEV=1` or `--windowed`, and never hard-code Pi-only paths outside config.

## Tech Stack

- **Language:** Python 3.11+
- **UI:** pygame-ce (SDL2)
- **Web server:** FastAPI + Uvicorn, run in a background thread or a separate systemd service
- **Storage:** SQLite (`library.db`) for the library index; TOML files for per-game manifests
- **Config:** a single `config.toml`
- **Packaging:** `pyproject.toml`, installed into a venv at `/opt/retro99`
- **Tests:** pytest

Keep dependencies minimal. No Electron and no heavy web frameworks on the front end of the web UI; use plain HTML/CSS/vanilla JS.

## Directory Layout

```
retro99/
├── CLAUDE.md
├── pyproject.toml
├── config.example.toml
├── retro99/
│   ├── __main__.py          # entry point
│   ├── app.py               # main loop, screen stack
│   ├── render/
│   │   ├── textgrid.py      # 80x25 character-cell renderer
│   │   ├── palette.py       # CGA/EGA 16-color palette
│   │   ├── widgets.py       # windows, menus, lists, dialogs (box-drawing)
│   │   └── crt.py           # optional scanline/curvature post-process
│   ├── screens/             # boot, main library, game detail, settings, prompt
│   ├── library/
│   │   ├── scanner.py       # walks game dirs, builds index
│   │   ├── manifest.py      # game.toml read/write + validation
│   │   ├── systems.py       # system definitions (extensions, launchers)
│   │   └── db.py            # SQLite access
│   ├── launch/
│   │   ├── base.py          # Launcher interface
│   │   ├── emulator.py      # DOSBox-Staging, RetroArch cores, standalone emus
│   │   ├── native.py        # source ports
│   │   └── wine.py          # Box64 + Wine
│   ├── ingest/
│   │   ├── importer.py      # shared import pipeline (web, USB, Samba)
│   │   ├── detect.py        # system detection by extension/header/size
│   │   └── convert.py       # BIN/CUE -> CHD via chdman, unzip/7z
│   ├── input/               # keyboard + gamepad mapping, exit hotkey watcher
│   ├── web/
│   │   ├── server.py        # FastAPI app
│   │   └── static/          # DOS-styled HTML/CSS/JS
│   └── hw/
│       └── gpio.py          # power button, LED, NFC cartridge reader (optional)
├── assets/
│   ├── fonts/               # Px437 IBM VGA 8x16 (Oldschool PC Font Pack, CC BY-SA 4.0)
│   └── sounds/              # PC-speaker-style beeps
├── deploy/
│   ├── retro99.service
│   ├── retro99-web.service
│   └── install.sh
└── tests/
```

## Data Layout on the Pi

```
/srv/retro99/
├── games/
│   ├── dos/<game-id>/          # DOS bundles
│   ├── native/<game-id>/       # source-port game data
│   ├── windows/<game-id>/      # Wine prefix + game files
│   └── roms/<system>/          # console ROMs and disc images
├── bios/<system>/              # user-supplied BIOS files
├── media/<game-id>/            # box art, screenshots, dithered EGA versions
├── saves/                      # save states / save files (per emulator)
├── inbox/                      # staging area for uploads before import
└── library.db
```

## Game Manifest (`game.toml`)

Every non-ROM game (DOS, native, Windows) has a `game.toml` in its folder. Console ROMs get a manifest auto-generated on import, stored in the DB and optionally sidecar files.

```toml
id = "duke3d"
title = "Duke Nukem 3D"
year = 1996
publisher = "3D Realms"
system = "dos"             # dos | native | windows | nes | snes | genesis | psx | ...
launcher = "native"        # emulator | native | wine
genre = "FPS"
players = "1"
favorite = false
notes = ""

[launch]
program = "eduke32"        # key into config.toml [programs]
args = ["-g", "{game_dir}/DUKE3D.GRP"]
cwd = "{game_dir}"

[input]
exit_combo = "default"     # or a custom combo
```

DOS bundle example:

```toml
id = "soda-offroad"
title = "SODA Off-Road Racing"
system = "dos"
launcher = "emulator"

[launch]
program = "dosbox-staging"
args = ["-conf", "{game_dir}/dosbox.conf"]
cwd = "{game_dir}"
```

A DOS bundle folder contains `C/` (the installed game), `cd/` (CUE/BIN images), and `dosbox.conf` with an `[autoexec]` that mounts C:, imgmounts D:, and runs the game.

**Placeholders** the launcher must expand: `{game_dir}`, `{rom_path}`, `{bios_dir}`, `{saves_dir}`, `{system}`.

Validate manifests on load. A bad manifest shows the game in the list with a red `[!]` marker and an error in the detail pane; it must never crash the launcher.

## Launcher Types

All launchers implement:

```python
class Launcher(Protocol):
    def build_command(self, game: Game) -> LaunchSpec: ...  # argv, env, cwd
    def preflight(self, game: Game) -> list[str]: ...  # missing BIOS/files/programs
```

- **emulator:** DOSBox-Staging, RetroArch (`retroarch -L <core> <rom>`), and standalone emulators (PPSSPP, Flycast)
- **native:** source ports (EDuke32, Xash3D FWGS). The port binary comes from config; the game supplies data.
- **wine:** runs via Box64 + Wine with a per-game `WINEPREFIX`. Env vars (e.g. `BOX64_*`, `WINEDEBUG=-all`) are configurable per game.

Launch procedure:
1. Run `preflight`; if anything is missing, show a DOS-style error dialog and don't launch.
2. Show a "Loading..." screen.
3. Release the display (quit the pygame display) so the child process gets DRM/KMS.
4. Spawn the child with `subprocess.Popen` and start the exit-hotkey watcher.
5. On child exit, reinit the display, update "last played" and play time, and return to the library.
6. Log the child's stdout/stderr to `/var/log/retro99/<game-id>.log`.

**Exit hotkey:** a global watcher (reading evdev directly, since the child owns the display) that kills the child's process group on a configurable combo (default: Select + Start held for 2 seconds). Send SIGTERM, then SIGKILL after 3 seconds.

## Systems Definition

Systems live in `config.toml` so new ones can be added without code changes:

```toml
[systems.snes]
name = "Super Nintendo"
extensions = [".sfc", ".smc", ".zip"]
launcher = "emulator"
program = "retroarch"
core = "snes9x"
bios = []

[systems.psx]
name = "PlayStation"
extensions = [".chd", ".cue", ".pbp"]
launcher = "emulator"
program = "retroarch"
core = "pcsx_rearmed"
bios = ["scph5501.bin"]
```

Ship defaults for: NES, SNES, Genesis/Mega Drive, Master System, Game Boy/GBC/GBA, N64, PS1, Sega CD, Saturn, Dreamcast, PSP, TurboGrafx-16, arcade (FBNeo), plus `dos`, `native`, and `windows`. Mark Saturn and N64 as `performance = "variable"` so the UI can show a note.

## ROM & Game Ingestion

One shared pipeline, used by every entry point:

1. A file lands in `/srv/retro99/inbox/` (from web upload, USB auto-import, or the Samba share).
2. Extract archives (`.zip`, `.7z`) unless the system's core loads zips directly (arcade, most cartridge systems).
3. Detect the system: by the user's choice in the upload form if given; otherwise by extension, then by header/size heuristics for ambiguous extensions (`.bin`, `.iso`).
4. Convert disc images: BIN/CUE and ISO go to CHD via `chdman createcd`, keeping the original only if `keep_originals = true`.
5. Handle multi-disc games: group `(Disc 1)`, `(Disc 2)`, etc. into an `.m3u` playlist automatically.
6. Normalize the title: strip No-Intro/Redump tags like `(USA)` and `[!]` for display, and keep the region as metadata.
7. Deduplicate by hash (CRC32 or SHA1). If the game already exists, say so and skip it.
8. Move the file into `games/roms/<system>/`, index it in SQLite, and report the result.

DOS, native, and Windows games are uploaded as a zipped bundle folder containing a `game.toml`. If `game.toml` is missing, the web UI offers a form to create one.

Every import step must be idempotent and must leave the inbox clean or clearly report what failed. Imports never block the UI thread.

## UI Design: The DOS Look

**Rendering**
- Logical screen: an **80×25 character grid** using an 8×16 VGA bitmap font (640×400 native), integer-scaled to the display with letterboxing
- **Colors:** only the 16-color CGA/EGA palette, defined once in `palette.py`
- **Borders:** CP437 box-drawing characters (single and double lines); drop shadows as dark cells offset one row down and two columns right, like Turbo Vision
- **Cursor:** a blinking block cursor wherever text is editable

**Main screen layout**
```
┌─ RETRO-99 ──────────────────────────────── 12:18 ─┐   <- menu bar: File  Systems  Options  Help
│ Systems        │ Games                   │ Details  │
│ ► DOS          │   Duke Nukem 3D   1996  │ [art]    │
│   Windows      │ ► Half-Life       1998  │ Year...  │
│   SNES  ...    │   StarCraft       1998  │ Plays... │
└───────────────────────────────────────────────────┘
 F1 Help  F2 Fav  F3 Info  F5 Rescan  F10 Menu        <- function-key bar
```
- Three panes: systems, the game list, and details
- Letter-jump in the list (press a letter to jump to the first title starting with it)
- Filters: favorites, recently played, and all
- Details pane: box art dithered to the EGA palette (use Floyd–Steinberg; cache the result in `media/`), year, publisher, play time, last played, and any preflight warnings

**Signature touches (each one toggleable in settings)**
- **Boot sequence:** a fake BIOS POST with a memory count-up, then "Starting MS-DOS...", then `C:\>` typing `RETRO99.EXE` before the UI appears. Skippable with any key; auto-skipped after the first boot of the day, if enabled.
- **CRT shader:** scanlines and slight curvature, as a post-process. Off by default.
- **Sounds:** PC-speaker-style beeps on navigation and errors
- **Command prompt:** `F10 > Exit to DOS` opens a fake `C:\>` prompt supporting `DIR`, `CD`, `CLS`, `HELP`, `VER`, and running a game by its ID. `EXIT` returns to the UI.

**Screen stack:** screens push and pop (library → detail → settings). ESC or the gamepad B button always goes back one level.

## Input

- Full navigation with the keyboard only, and with a gamepad only
- Gamepad mapping through SDL's GameController API; D-pad/stick to move, A = select, B = back, X = favorite, Y = details, Start = menu
- Key repeat with acceleration for long lists
- The TI-99/4A original keyboard will appear as a standard USB HID keyboard through an RP2040 converter. Nothing special is needed in the code, but avoid depending on keys the TI lacks (it has no F-keys natively) for **essential** actions. Every function-key action must also be reachable from the menu bar.

## Web Management UI

- Served on port 8099 on the LAN, with no auth by default and an optional password in config
- Styled to match: blue background, VGA web font, box-drawing panels, and monospace throughout
- Pages:
  - **Library:** browse, search, edit metadata, delete (with confirmation), and upload box art
  - **Upload:** drag and drop multiple files, an optional system selector, and a per-file progress and result log that streams from the import pipeline
  - **BIOS:** shows which BIOS files each system needs, which are present, and a hash check against known-good hashes where available
  - **System:** disk space, temperature, uptime, and buttons to rescan the library and restart the launcher
- Chunked uploads so multi-GB disc images work
- API endpoints under `/api/`, documented automatically by FastAPI's OpenAPI page

## Hardware Integration (Phase 5, optional)

- **Power button** (GPIO): short press = clean shutdown, with a "Shutting down..." DOS-style screen
- **Power LED** (GPIO): on while running, blinks during imports
- **NFC cartridges:** a PN532 or RC522 reader behind the TI cartridge slot. A tag's UID maps to a game ID in `config.toml [cartridges]`. Inserting a cartridge launches the game; removing it returns to the menu (configurable). Include a "pair cartridge" flow in settings: scan an unknown tag, then pick a game.
- All hardware code sits behind `hw/`, and is disabled cleanly when the hardware or `gpiod` isn't present (always disabled in dev mode).

## Development Phases

Build and verify each phase before moving on. Each phase ends with working, tested code.

1. **Renderer:** text grid, palette, font, widgets (window, list, dialog, menu bar), runs windowed on desktop, demo screen
2. **Library:** manifest parsing and validation, systems config, scanner, SQLite index, the three-pane main screen with real data
3. **Launching:** all three launcher types, preflight checks, display release/reinit, exit-hotkey watcher, logging
4. **Input:** full gamepad support, key repeat, letter-jump, settings screen
5. **Ingestion + web UI:** import pipeline, CHD conversion, m3u grouping, dedup, FastAPI server, DOS-styled pages
6. **Pi deployment:** systemd units, `install.sh`, KMS/DRM fullscreen, boot sequence, performance check
7. **Hardware:** GPIO power button and LED, NFC cartridges

## Coding Conventions

- Type hints everywhere; `ruff` for lint and format
- No global state outside `app.py`; pass config and the DB handle explicitly
- All paths come from `config.toml`; use `pathlib` throughout
- Logging via the `logging` module to `/var/log/retro99/` (or `./logs/` in dev mode)
- Pure logic (manifest parsing, detection, title normalization, placeholder expansion, command building) must be unit-tested without a display or real emulators
- UI code must never block: imports, scans, and hashing run in worker threads with progress reported back through a queue

## Testing

- Unit tests for everything under `library/`, `ingest/`, and `launch/` (command building only; mock `subprocess`)
- Fixture folder `tests/fixtures/` with tiny fake ROMs, sample manifests (valid and broken), and sample CUE sheets
- A `--dry-run` launch flag that prints the command it would run instead of running it
- A headless smoke test that starts the app with the SDL dummy video driver, renders each screen once, and exits

## Out of Scope

- Writing or bundling emulators, BIOS files, or games
- Downloading ROMs from the internet
- Online metadata scraping in v1 (manual metadata and art only; design `library/` so a scraper can be added later)
- Save-state management UI (emulators handle their own saves; the launcher only sets the save directories)

## Reference: Known Game Setups

These are the initial test titles. Each one exercises a different launcher path.

| Game | Launcher | Program | Notes |
|---|---|---|---|
| Duke Nukem 3D | native | EDuke32 | Needs `DUKE3D.GRP` from the CD |
| Half-Life | native | Xash3D FWGS | Needs the `valve/` folder from an installed copy |
| StarCraft | wine | Box64 + Wine | Per-game `WINEPREFIX`; the most setup-heavy title |
| SODA Off-Road Racing | emulator | DOSBox-Staging | Performance unverified on Pi 5; may need cycles tuning. If the copy requires Windows 95, switch to the wine launcher. |
