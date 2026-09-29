"""The ``Game`` record shared by the scanner, the database and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from retro99.library.names import sort_key


@dataclass
class Game:
    id: str
    kind: str  # "bundle" (folder with game.toml) or "rom" (single file)
    system: str
    title: str
    path: Path  # bundle folder, or the ROM / playlist file
    year: int | None = None
    publisher: str = ""
    genre: str = ""
    players: str = ""
    region: str = ""
    launcher: str = ""
    program: str = ""
    notes: str = ""
    favorite: bool = False
    error: str = ""  # non-empty: shown with a red [!] and never launched
    manifest: dict[str, Any] = field(default_factory=dict)
    # Owned by the database; the scanner never sets these.
    play_seconds: int = 0
    play_count: int = 0
    last_played: datetime | None = None
    added_at: datetime | None = None

    @property
    def sort_title(self) -> str:
        return sort_key(self.title)

    @property
    def is_rom(self) -> bool:
        return self.kind == "rom"


def format_play_time(seconds: int) -> str:
    if seconds <= 0:
        return "never"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{max(minutes, 1)}m"
