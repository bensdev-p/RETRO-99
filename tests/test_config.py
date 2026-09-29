from pathlib import Path

from retro99.config import PROJECT_ROOT, load_config, parse_config, set_data_root


def test_defaults_are_relative_to_project_root():
    cfg = parse_config({}, dev=False)
    assert cfg.display.fullscreen is True
    assert cfg.paths.data_root == PROJECT_ROOT / "data"
    assert cfg.paths.fonts[0] == PROJECT_ROOT / "assets/fonts/PxPlus_IBM_VGA_8x16.ttf"
    assert cfg.paths.games_dir == PROJECT_ROOT / "data/games"
    assert cfg.paths.db == PROJECT_ROOT / "data/library.db"
    assert cfg.library.scan_on_start is True
    assert "snes" in cfg.systems


def test_dev_mode_forces_windowed_and_local_logs():
    cfg = parse_config(
        {"display": {"fullscreen": True}, "paths": {"log_dir": "/var/log/x"}}, dev=True
    )
    assert cfg.display.fullscreen is False
    assert cfg.paths.log_dir == PROJECT_ROOT / "logs"


def test_load_from_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        "[display]\nwindow_scale = 3\n[ui]\ncrt = true\n"
        '[paths]\ndata_root = "/srv/retro99"\nfonts = ["/x/font.psf"]\n'
    )
    cfg = load_config(path)
    assert cfg.source == path
    assert cfg.display.window_scale == 3
    assert cfg.ui.crt is True
    assert cfg.paths.data_root == Path("/srv/retro99")
    assert cfg.paths.fonts == [Path("/x/font.psf")]


def test_example_config_parses():
    cfg = load_config(PROJECT_ROOT / "config.example.toml")
    assert cfg.paths.data_root == Path("/srv/retro99")
    assert cfg.paths.log_dir == Path("/var/log/retro99")
    assert cfg.paths.games_dir == Path("/srv/retro99/games")
    assert cfg.paths.media_dir == Path("/srv/retro99/media")


def test_path_overrides_systems_and_data_root(tmp_path):
    cfg = parse_config(
        {
            "paths": {"data_root": "/srv/r", "media_dir": "/mnt/art"},
            "library": {"scan_on_start": False},
            "systems": {"snes": {"core": "bsnes"}},
        },
        dev=False,
    )
    assert cfg.paths.games_dir == Path("/srv/r/games")
    assert cfg.paths.media_dir == Path("/mnt/art")
    assert cfg.library.scan_on_start is False
    assert cfg.systems["snes"].core == "bsnes"
    set_data_root(cfg, tmp_path)
    assert cfg.paths.db == tmp_path / "library.db"
