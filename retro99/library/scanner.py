"""Walks the games folders and builds ``Game`` records. Pure filesystem work: it
never touches the display, so it runs in a worker thread and reports progress
through a callback.

Layout (under ``games_dir``):

* ``<category>/<folder>/game.toml`` for DOS, native and Windows bundles. The
  manifest's ``system`` decides where the game is listed.
* ``roms/<system>/...`` for console ROMs, matched by the system's extensions.
  ``.m3u`` playlists hide the discs they list, a ``<rom stem>.toml`` sidecar
  may supply metadata, and hidden files are ignored.
"""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retro99.library.manifest import MANIFEST_NAME, load_manifest
from retro99.library.models import Game
from retro99.library.names import parse_name, slugify
from retro99.library.systems import System

log = logging.getLogger(__name__)

ROMS_DIR = "roms"
_SIDECAR_FIELDS = ("title", "year", "publisher", "genre", "players", "notes")

Progress = Callable[[int, int, str], None]  # (done, total, current item)


@dataclass
class ScanResult:
    games: list[Game] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Game]:
        return [g for g in self.games if g.error]


def _visible(path: Path) -> bool:
    return not path.name.startswith(".")


def scan_bundle(folder: Path, systems: Mapping[str, System]) -> Game:
    result = load_manifest(folder / MANIFEST_NAME, systems)
    data = result.data
    m = result.manifest
    if m is not None:
        return Game(
            id=m.id,
            kind="bundle",
            system=m.system,
            title=m.title,
            path=folder,
            year=m.year,
            publisher=m.publisher,
            genre=m.genre,
            players=m.players,
            launcher=m.launcher,
            program=m.program,
            notes=m.notes,
            favorite=m.favorite,
            manifest=data,
        )
    # Broken manifest: list it anyway with whatever could be read.
    system = data.get("system") if isinstance(data.get("system"), str) else ""
    if system not in systems:
        system = folder.parent.name if folder.parent.name in systems else "dos"
    title = data.get("title") if isinstance(data.get("title"), str) else folder.name
    year = data.get("year") if isinstance(data.get("year"), int) else None
    return Game(
        id=slugify(folder.name),
        kind="bundle",
        system=system,
        title=title or folder.name,
        path=folder,
        year=year,
        error="; ".join(result.errors),
        manifest=data,
    )


def _playlist_members(m3u: Path) -> set[Path]:
    members = set()
    try:
        for line in m3u.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                members.add((m3u.parent / line).resolve())
    except OSError as e:
        log.warning("cannot read playlist %s: %s", m3u, e)
    return members


def _read_sidecar(rom: Path) -> tuple[dict[str, Any], str]:
    sidecar = rom.with_suffix(".toml")
    if not sidecar.is_file():
        return {}, ""
    try:
        with sidecar.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {}, f"{sidecar.name}: {e}"
    return {k: data[k] for k in _SIDECAR_FIELDS if k in data}, ""


def scan_rom(rom: Path, system: System) -> Game:
    parsed = parse_name(rom.stem)
    meta, error = _read_sidecar(rom)
    title = meta.get("title") if isinstance(meta.get("title"), str) else parsed.title
    year = meta.get("year")
    return Game(
        id=f"{system.key}-{slugify(rom.stem)}",
        kind="rom",
        system=system.key,
        title=title,
        path=rom,
        year=year if isinstance(year, int) and not isinstance(year, bool) else None,
        publisher=str(meta.get("publisher", "")),
        genre=str(meta.get("genre", "")),
        players=str(meta.get("players", "")),
        notes=str(meta.get("notes", "")),
        region=parsed.region,
        launcher=system.launcher,
        program=system.program,
        error=error,
        manifest={
            "title": title,
            "system": system.key,
            "launcher": system.launcher,
            "region": parsed.region,
            "rom": rom.name,
            **{k: v for k, v in meta.items() if k != "title"},
        },
    )


def _rom_files(system_dir: Path, system: System) -> list[Path]:
    files = sorted(
        p
        for p in system_dir.rglob("*")
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(system_dir).parts)
        and system.matches(p.name)
    )
    hidden: set[Path] = set()
    for f in files:
        if f.suffix.lower() == ".m3u":
            hidden |= _playlist_members(f)
    return [f for f in files if f.resolve() not in hidden]


def scan_library(
    games_dir: Path,
    systems: Mapping[str, System],
    progress: Progress | None = None,
) -> ScanResult:
    result = ScanResult()
    if not games_dir.is_dir():
        result.warnings.append(f"games folder not found: {games_dir}")
        return result

    # Collect work first so progress has a total.
    bundles: list[Path] = []
    roms: list[tuple[Path, System]] = []
    for category in sorted(p for p in games_dir.iterdir() if p.is_dir() and _visible(p)):
        if category.name == ROMS_DIR:
            for system_dir in sorted(p for p in category.iterdir() if p.is_dir() and _visible(p)):
                system = systems.get(system_dir.name)
                if system is None or system.kind != "rom":
                    result.warnings.append(f"unknown ROM system folder: {system_dir.name}")
                    continue
                roms.extend((f, system) for f in _rom_files(system_dir, system))
        else:
            bundles.extend(sorted(p for p in category.iterdir() if p.is_dir() and _visible(p)))

    total = len(bundles) + len(roms)
    seen: dict[str, Path] = {}
    done = 0

    def add(game: Game) -> None:
        nonlocal done
        if game.id in seen:
            other = seen[game.id]
            n = 2
            while f"{game.id}~{n}" in seen:
                n += 1
            game.error = "; ".join(
                filter(None, [game.error, f"duplicate id '{game.id}' (also used by {other})"])
            )
            game.id = f"{game.id}~{n}"
        seen[game.id] = game.path
        result.games.append(game)
        done += 1
        if progress:
            progress(done, total, game.title)

    for folder in bundles:
        add(scan_bundle(folder, systems))
    for rom, system in roms:
        add(scan_rom(rom, system))

    for w in result.warnings:
        log.warning("scan: %s", w)
    log.info("scan: %d games (%d with errors)", len(result.games), len(result.errors))
    return result
