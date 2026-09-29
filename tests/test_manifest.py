import tomllib

import pytest

from retro99.library.manifest import (
    dump_manifest,
    load_manifest,
    parse_manifest,
    placeholders_in,
    set_top_level_key,
    write_favorite,
)
from retro99.library.systems import DEFAULT_SYSTEMS

GAMES = __import__("pathlib").Path(__file__).parent / "fixtures" / "library" / "games"


def valid(**overrides):
    data = {
        "id": "duke3d",
        "title": "Duke Nukem 3D",
        "system": "dos",
        "launcher": "native",
        "launch": {"program": "eduke32", "args": ["-g", "{game_dir}/DUKE3D.GRP"]},
    }
    data.update(overrides)
    return data


def test_spec_example_manifest_loads():
    result = load_manifest(GAMES / "dos/duke3d/game.toml", DEFAULT_SYSTEMS)
    assert result.ok
    m = result.manifest
    assert (m.id, m.title, m.year, m.system, m.launcher) == (
        "duke3d", "Duke Nukem 3D", 1996, "dos", "native",
    )  # fmt: skip
    assert m.args == ["-g", "{game_dir}/DUKE3D.GRP"]
    assert m.cwd == "{game_dir}" and m.exit_combo == "default"


def test_wine_env_and_int_players():
    sc = load_manifest(GAMES / "windows/starcraft/game.toml", DEFAULT_SYSTEMS).manifest
    assert sc.env["WINEPREFIX"] == "{game_dir}" and sc.favorite is True
    hl = load_manifest(GAMES / "native/half-life/game.toml", DEFAULT_SYSTEMS).manifest
    assert hl.players == "1"


def test_syntax_error_is_reported_not_raised():
    result = load_manifest(GAMES / "dos/broken-syntax/game.toml")
    assert result.manifest is None
    assert "not valid TOML" in result.errors[0]


def test_missing_file():
    result = load_manifest(GAMES / "dos/no-manifest/game.toml")
    assert result.errors == ["no game.toml in this folder"]


def test_bad_fields_collects_every_error():
    result = load_manifest(GAMES / "windows/bad-fields/game.toml", DEFAULT_SYSTEMS)
    text = "\n".join(result.errors)
    assert "id 'Bad Fields!'" in text
    assert "missing required field 'title'" in text
    assert "launcher must be one of" in text
    assert "year must be" in text
    assert "unknown placeholder {exe_name}" in text
    assert result.data["system"] == "windows"  # partial data kept for display


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"system": "amiga"}, "unknown system 'amiga'"),
        ({"launch": "eduke32"}, "missing [launch] table"),
        ({"launch": {"args": []}}, "launch.program"),
        ({"launch": {"program": "x", "args": "-g"}}, "list of strings"),
        ({"launch": {"program": "x", "env": {"A": 1}}}, "table of strings"),
        ({"launch": {"program": "x", "cwd": "{nope}"}}, "unknown placeholder {nope}"),
        ({"favorite": "yes"}, "'favorite'"),
        ({"year": True}, "year"),
        ({"publisher": 3}, "'publisher'"),
        ({"input": {"exit_combo": 5}}, "exit_combo"),
    ],
)
def test_validation_errors(overrides, error):
    result = parse_manifest(valid(**overrides), DEFAULT_SYSTEMS)
    assert not result.ok
    assert any(error in e for e in result.errors), result.errors


def test_placeholders():
    assert placeholders_in("{game_dir}/x {rom_path}") == ["game_dir", "rom_path"]
    assert placeholders_in("{{literal}}") == []
    assert placeholders_in("{oops") == ["<malformed braces>"]


def test_dump_round_trips():
    data = valid(year=1996, favorite=True, notes='say "hi"\n', launch={
        "program": "wine", "args": ["a b"], "env": {"WINEDEBUG": "-all"},
    })  # fmt: skip
    assert tomllib.loads(dump_manifest(data)) == data


def test_set_top_level_key_keeps_comments_and_tables():
    text = 'id = "x"\nfavorite = false  # star\n\n[launch]\nfavorite = 1\n'
    assert set_top_level_key(text, "favorite", True) == (
        'id = "x"\nfavorite = true  # star\n\n[launch]\nfavorite = 1\n'
    )
    added = set_top_level_key('id = "x"\n\n[launch]\nprogram = "p"\n', "favorite", True)
    assert added == 'id = "x"\nfavorite = true\n\n[launch]\nprogram = "p"\n'
    assert set_top_level_key('id = "x"', "favorite", False) == 'id = "x"\nfavorite = false\n'


def test_write_favorite(tmp_path):
    path = tmp_path / "game.toml"
    path.write_text((GAMES / "dos/duke3d/game.toml").read_text())
    write_favorite(path, True)
    reloaded = load_manifest(path, DEFAULT_SYSTEMS)
    assert reloaded.manifest.favorite is True
    assert "# key into config.toml [programs]" in path.read_text()
