"""System definitions: which files belong to a system and how it launches.

Defaults ship here; ``[systems.<key>]`` tables in config.toml override fields
of a default system or add new systems, so no code change is needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields, replace
from typing import Any

log = logging.getLogger(__name__)

LAUNCHERS = ("emulator", "native", "wine")


@dataclass(frozen=True)
class System:
    key: str
    name: str
    short: str = ""  # fits the 15-column systems pane
    kind: str = "rom"  # "rom": files under games/roms/<key>/; "bundle": folders with game.toml
    extensions: tuple[str, ...] = ()
    launcher: str = "emulator"
    program: str = ""
    core: str = ""
    bios: tuple[str, ...] = ()
    performance: str = ""  # "variable" shows a note in the details pane

    @property
    def label(self) -> str:
        return self.short or self.name

    def matches(self, filename: str) -> bool:
        lower = filename.lower()
        return any(lower.endswith(ext) for ext in self.extensions)


def _rom(
    key: str,
    name: str,
    short: str,
    exts: str,
    program: str,
    core: str = "",
    bios: tuple[str, ...] = (),
    performance: str = "",
) -> System:
    return System(
        key, name, short, "rom", tuple(exts.split()), "emulator", program, core, bios, performance
    )


DEFAULT_SYSTEMS: dict[str, System] = {
    s.key: s
    for s in (
        System("dos", "MS-DOS", "DOS", "bundle", launcher="emulator", program="dosbox-staging"),
        System("windows", "Windows 9x", "Windows", "bundle", launcher="wine", program="wine"),
        System("native", "Native Ports", "Native Ports", "bundle", launcher="native"),
        _rom("nes", "Nintendo Entertainment System", "NES", ".nes .zip", "retroarch", "fceumm"),
        _rom("snes", "Super Nintendo", "SNES", ".sfc .smc .zip", "retroarch", "snes9x"),
        _rom(
            "genesis",
            "Sega Genesis / Mega Drive",
            "Genesis",
            ".md .gen .smd .bin .zip",
            "retroarch",
            "genesis_plus_gx",
        ),
        _rom(
            "mastersystem",
            "Sega Master System",
            "Master System",
            ".sms .zip",
            "retroarch",
            "genesis_plus_gx",
        ),
        _rom("gb", "Game Boy", "Game Boy", ".gb .zip", "retroarch", "gambatte"),
        _rom("gbc", "Game Boy Color", "Game Boy Color", ".gbc .zip", "retroarch", "gambatte"),
        _rom("gba", "Game Boy Advance", "GB Advance", ".gba .zip", "retroarch", "mgba"),
        _rom(
            "n64",
            "Nintendo 64",
            "N64",
            ".n64 .z64 .v64 .zip",
            "retroarch",
            "mupen64plus_next",
            performance="variable",
        ),
        _rom(
            "psx",
            "PlayStation",
            "PlayStation",
            ".chd .cue .pbp .m3u",
            "retroarch",
            "pcsx_rearmed",
            ("scph5501.bin",),
        ),
        _rom(
            "segacd",
            "Sega CD / Mega-CD",
            "Sega CD",
            ".chd .cue .m3u",
            "retroarch",
            "genesis_plus_gx",
            ("bios_CD_U.bin",),
        ),
        _rom(
            "saturn",
            "Sega Saturn",
            "Saturn",
            ".chd .cue .m3u",
            "retroarch",
            "yabasanshiro",
            performance="variable",
        ),
        _rom("dreamcast", "Sega Dreamcast", "Dreamcast", ".chd .cdi .gdi .m3u", "flycast"),
        _rom("psp", "PlayStation Portable", "PSP", ".iso .cso .chd .pbp", "ppsspp"),
        _rom(
            "pcengine",
            "TurboGrafx-16 / PC Engine",
            "TurboGrafx-16",
            ".pce .zip",
            "retroarch",
            "mednafen_pce_fast",
        ),
        _rom("arcade", "Arcade (FBNeo)", "Arcade", ".zip .7z", "retroarch", "fbneo"),
    )
}

_FIELD_NAMES = {f.name for f in fields(System)} - {"key"}


def _coerce(key: str, name: str, value: Any) -> Any:
    if name in ("extensions", "bios"):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"systems.{key}.{name} must be a list of strings")
        if name == "extensions":
            return tuple(v.lower() if v.startswith(".") else f".{v.lower()}" for v in value)
        return tuple(value)
    if not isinstance(value, str):
        raise ValueError(f"systems.{key}.{name} must be a string")
    if name == "launcher" and value not in LAUNCHERS:
        raise ValueError(f"systems.{key}.launcher must be one of {', '.join(LAUNCHERS)}")
    if name == "kind" and value not in ("rom", "bundle"):
        raise ValueError(f"systems.{key}.kind must be 'rom' or 'bundle'")
    return value


def load_systems(tables: dict[str, Any] | None) -> dict[str, System]:
    """Merge ``[systems.*]`` config tables over the defaults. Bad entries are logged and
    skipped so a typo in config.toml never stops the launcher."""
    systems = dict(DEFAULT_SYSTEMS)
    for key, table in (tables or {}).items():
        if not isinstance(table, dict):
            log.warning("config: systems.%s is not a table; ignored", key)
            continue
        try:
            updates = {}
            for name, value in table.items():
                if name not in _FIELD_NAMES:
                    log.warning("config: unknown field systems.%s.%s ignored", key, name)
                    continue
                updates[name] = _coerce(key, name, value)
        except ValueError as e:
            log.warning("config: %s; system ignored", e)
            continue
        if key in systems:
            systems[key] = replace(systems[key], **updates)
        elif "name" not in updates:
            log.warning("config: new system systems.%s needs a name; ignored", key)
        else:
            systems[key] = System(key=key, **updates)
    return systems
