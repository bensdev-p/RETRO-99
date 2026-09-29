from pathlib import Path

from retro99.config import PROJECT_ROOT, load_config, parse_config


def test_defaults_are_relative_to_project_root():
    cfg = parse_config({}, dev=False)
    assert cfg.display.fullscreen is True
    assert cfg.paths.data_root == PROJECT_ROOT / "data"
    assert cfg.paths.fonts[0] == PROJECT_ROOT / "assets/fonts/Px437_IBM_VGA_8x16.ttf"


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
