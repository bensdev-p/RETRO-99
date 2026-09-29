from retro99.library.scanner import scan_library
from retro99.library.systems import DEFAULT_SYSTEMS


def by_id(result):
    return {g.id: g for g in result.games}


def test_scan_finds_bundles_and_roms(library_root):
    progress = []
    result = scan_library(library_root / "games", DEFAULT_SYSTEMS,
                          lambda d, t, c: progress.append((d, t)))  # fmt: skip
    games = by_id(result)
    assert {"duke3d", "soda-offroad", "half-life", "starcraft"} <= set(games)
    assert games["duke3d"].system == "dos" and games["duke3d"].launcher == "native"
    assert games["half-life"].system == "native"
    assert games["starcraft"].favorite is True
    assert progress[-1] == (len(result.games), len(result.games))


def test_broken_bundles_are_listed_with_errors(library_root):
    games = by_id(scan_library(library_root / "games", DEFAULT_SYSTEMS))
    assert "not valid TOML" in games["broken-syntax"].error
    assert games["broken-syntax"].title == "broken-syntax"
    assert "no game.toml" in games["no-manifest"].error
    bad = games["bad-fields"]
    assert bad.system == "windows" and "unknown placeholder" in bad.error


def test_roms_are_normalized(library_root):
    games = by_id(scan_library(library_root / "games", DEFAULT_SYSTEMS))
    quest = games["snes-super-fake-quest-usa"]
    assert (quest.title, quest.region, quest.kind) == ("Super Fake Quest", "USA", "rom")
    assert quest.program == "retroarch"
    assert games["snes-legend-of-fakeland-the-japan"].title == "The Legend of Fakeland"


def test_hidden_files_other_extensions_and_unknown_systems_skipped(library_root):
    result = scan_library(library_root / "games", DEFAULT_SYSTEMS)
    snes = [g for g in result.games if g.system == "snes"]
    assert len(snes) == 2  # readme.txt and .hidden/ ignored
    assert any("unknownsys" in w for w in result.warnings)


def test_m3u_hides_member_discs(library_root):
    psx = [g for g in scan_library(library_root / "games", DEFAULT_SYSTEMS).games
           if g.system == "psx"]  # fmt: skip
    assert sorted(g.path.name for g in psx) == ["Fake Saga (USA).m3u", "Solo Disc (Europe).chd"]
    assert {g.title for g in psx} == {"Fake Saga", "Solo Disc"}


def test_sidecar_metadata(library_root):
    tiny = by_id(scan_library(library_root / "games", DEFAULT_SYSTEMS))["nes-tiny-game-usa"]
    assert (tiny.title, tiny.year, tiny.publisher, tiny.players) == (
        "Tiny Game Deluxe", 1988, "Fake Soft", "1-2",
    )  # fmt: skip
    assert tiny.region == "USA"


def test_duplicate_ids_get_unique_keys_and_an_error(library_root):
    copy = library_root / "games/windows/duke-copy"
    copy.mkdir()
    (copy / "game.toml").write_text((library_root / "games/dos/duke3d/game.toml").read_text())
    games = by_id(scan_library(library_root / "games", DEFAULT_SYSTEMS))
    assert games["duke3d"].error == ""
    assert "duplicate id 'duke3d'" in games["duke3d~2"].error


def test_missing_games_dir(tmp_path):
    result = scan_library(tmp_path / "nope", DEFAULT_SYSTEMS)
    assert result.games == [] and "not found" in result.warnings[0]
