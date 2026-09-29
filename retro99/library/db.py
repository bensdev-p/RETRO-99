"""SQLite index of the library (``library.db``).

The scanner owns metadata; the database owns play statistics and, for ROMs,
the favorite flag (bundles keep ``favorite`` in their game.toml). Each thread
opens its own ``LibraryDB``: SQLite connections are not shared across threads.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from retro99.library.manifest import MANIFEST_NAME, write_favorite
from retro99.library.models import Game

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS games (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    system       TEXT NOT NULL,
    title        TEXT NOT NULL,
    sort_title   TEXT NOT NULL,
    path         TEXT NOT NULL,
    year         INTEGER,
    publisher    TEXT NOT NULL DEFAULT '',
    genre        TEXT NOT NULL DEFAULT '',
    players      TEXT NOT NULL DEFAULT '',
    region       TEXT NOT NULL DEFAULT '',
    launcher     TEXT NOT NULL DEFAULT '',
    program      TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    favorite     INTEGER NOT NULL DEFAULT 0,
    error        TEXT NOT NULL DEFAULT '',
    manifest     TEXT NOT NULL DEFAULT '{}',
    play_seconds INTEGER NOT NULL DEFAULT 0,
    play_count   INTEGER NOT NULL DEFAULT 0,
    last_played  TEXT,
    added_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS games_by_system ON games (system, sort_title);
"""

_META_COLUMNS = (
    "kind", "system", "title", "sort_title", "path", "year", "publisher", "genre", "players",
    "region", "launcher", "program", "notes", "error", "manifest",
)  # fmt: skip


@dataclass(frozen=True)
class SyncStats:
    added: int
    updated: int
    removed: int


class LibraryDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> LibraryDB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # writing ------------------------------------------------------------------
    def sync(self, games: Iterable[Game], now: datetime | None = None) -> SyncStats:
        """Make the index match a scan: upsert every game, drop the ones that vanished."""
        now_s = (now or datetime.now()).isoformat(timespec="seconds")
        cols = ", ".join(_META_COLUMNS)
        placeholders = ", ".join("?" for _ in _META_COLUMNS)
        updates = ", ".join(f"{c} = excluded.{c}" for c in _META_COLUMNS)
        sql = (
            f"INSERT INTO games (id, {cols}, favorite, added_at) VALUES (?, {placeholders}, ?, ?) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}, "
            "favorite = CASE WHEN excluded.kind = 'bundle' THEN excluded.favorite "
            "ELSE games.favorite END"
        )
        with self.conn:
            existing = {r[0] for r in self.conn.execute("SELECT id FROM games")}
            seen: set[str] = set()
            for g in games:
                seen.add(g.id)
                values = (
                    g.kind, g.system, g.title, g.sort_title, str(g.path), g.year, g.publisher,
                    g.genre, g.players, g.region, g.launcher, g.program, g.notes, g.error,
                    json.dumps(g.manifest, default=str),
                )  # fmt: skip
                self.conn.execute(sql, (g.id, *values, int(g.favorite), now_s))
            gone = existing - seen
            self.conn.executemany("DELETE FROM games WHERE id = ?", [(i,) for i in gone])
        return SyncStats(len(seen - existing), len(seen & existing), len(gone))

    def set_favorite(self, game: Game, favorite: bool) -> None:
        """Persist a favorite toggle (into game.toml too, for bundles)."""
        if game.kind == "bundle" and not game.error:
            try:
                write_favorite(game.path / MANIFEST_NAME, favorite)
            except (OSError, ValueError) as e:
                log.warning("could not update %s: %s", game.path / MANIFEST_NAME, e)
        with self.conn:
            self.conn.execute(
                "UPDATE games SET favorite = ? WHERE id = ?", (int(favorite), game.id)
            )
        game.favorite = favorite

    def record_play(self, game_id: str, seconds: int, when: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE games SET play_seconds = play_seconds + ?, play_count = play_count + 1, "
                "last_played = ? WHERE id = ?",
                (max(int(seconds), 0), when.isoformat(timespec="seconds"), game_id),
            )

    # reading ------------------------------------------------------------------
    @staticmethod
    def _game(row: sqlite3.Row) -> Game:
        return Game(
            id=row["id"],
            kind=row["kind"],
            system=row["system"],
            title=row["title"],
            path=Path(row["path"]),
            year=row["year"],
            publisher=row["publisher"],
            genre=row["genre"],
            players=row["players"],
            region=row["region"],
            launcher=row["launcher"],
            program=row["program"],
            notes=row["notes"],
            favorite=bool(row["favorite"]),
            error=row["error"],
            manifest=json.loads(row["manifest"] or "{}"),
            play_seconds=row["play_seconds"],
            play_count=row["play_count"],
            last_played=datetime.fromisoformat(row["last_played"]) if row["last_played"] else None,
            added_at=datetime.fromisoformat(row["added_at"]),
        )

    def _query(self, where: str = "", params: tuple = (), order: str = "sort_title") -> list[Game]:
        sql = "SELECT * FROM games" + (f" WHERE {where}" if where else "") + f" ORDER BY {order}"
        return [self._game(r) for r in self.conn.execute(sql, params)]

    def get(self, game_id: str) -> Game | None:
        games = self._query("id = ?", (game_id,))
        return games[0] if games else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    def system_counts(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT system, COUNT(*) FROM games GROUP BY system")
        return {system: n for system, n in rows}

    def all_games(self) -> list[Game]:
        return self._query()

    def games_for(self, system: str) -> list[Game]:
        return self._query("system = ?", (system,))

    def favorites(self) -> list[Game]:
        return self._query("favorite = 1")

    def recent(self, limit: int = 30) -> list[Game]:
        return self._query("last_played IS NOT NULL", order=f"last_played DESC LIMIT {int(limit)}")
