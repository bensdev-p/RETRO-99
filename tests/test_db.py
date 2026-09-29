from datetime import datetime

from retro99.library.db import LibraryDB
from retro99.library.manifest import load_manifest
from retro99.library.scanner import scan_library
from retro99.library.systems import DEFAULT_SYSTEMS

T0 = datetime(2026, 9, 1, 12, 0)


def scanned(root):
    return scan_library(root / "games", DEFAULT_SYSTEMS).games


def test_sync_add_update_remove(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        games = scanned(library_root)
        stats = db.sync(games, T0)
        assert stats.added == len(games) and stats.removed == 0
        assert db.count() == len(games)
        stats = db.sync([g for g in games if g.id != "duke3d"], T0)
        assert (stats.added, stats.updated, stats.removed) == (0, len(games) - 1, 1)
        assert db.get("duke3d") is None


def test_round_trip_fields(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        db.sync(scanned(library_root), T0)
        duke = db.get("duke3d")
        assert (duke.title, duke.year, duke.publisher, duke.kind) == (
            "Duke Nukem 3D", 1996, "3D Realms", "bundle",
        )  # fmt: skip
        assert duke.path == library_root / "games/dos/duke3d"
        assert duke.manifest["launch"]["program"] == "eduke32"
        assert duke.added_at == T0


def test_queries(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        db.sync(scanned(library_root), T0)
        counts = db.system_counts()
        assert counts["snes"] == 2 and counts["psx"] == 2
        assert [g.title for g in db.games_for("snes")] == [
            "The Legend of Fakeland", "Super Fake Quest",
        ]  # sorted ignoring "The"  # fmt: skip
        assert [g.id for g in db.favorites()] == ["starcraft"]
        assert db.recent() == []


def test_play_stats_survive_rescans(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        db.sync(scanned(library_root), T0)
        db.record_play("snes-super-fake-quest-usa", 125, T0)
        db.record_play("snes-super-fake-quest-usa", 60, datetime(2026, 9, 2))
        db.sync(scanned(library_root), T0)
        g = db.get("snes-super-fake-quest-usa")
        assert (g.play_seconds, g.play_count) == (185, 2)
        assert g.last_played == datetime(2026, 9, 2)
        assert [x.id for x in db.recent()] == ["snes-super-fake-quest-usa"]


def test_rom_favorite_lives_in_db(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        db.sync(scanned(library_root), T0)
        rom = db.get("nes-tiny-game-usa")
        db.set_favorite(rom, True)
        db.sync(scanned(library_root), T0)  # rescan must not reset it
        assert db.get("nes-tiny-game-usa").favorite is True


def test_bundle_favorite_writes_game_toml(library_root, tmp_path):
    with LibraryDB(tmp_path / "library.db") as db:
        db.sync(scanned(library_root), T0)
        duke = db.get("duke3d")
        db.set_favorite(duke, True)
        assert duke.favorite is True
        manifest = load_manifest(library_root / "games/dos/duke3d/game.toml").manifest
        assert manifest.favorite is True
        db.sync(scanned(library_root), T0)
        assert db.get("duke3d").favorite is True


def test_second_connection_sees_writes(library_root, tmp_path):
    path = tmp_path / "library.db"
    with LibraryDB(path) as ui, LibraryDB(path) as worker:
        worker.sync(scanned(library_root), T0)
        assert ui.count() > 0
