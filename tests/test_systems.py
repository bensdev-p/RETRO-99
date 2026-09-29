from retro99.library.systems import DEFAULT_SYSTEMS, load_systems

REQUIRED = [
    "nes", "snes", "genesis", "mastersystem", "gb", "gbc", "gba", "n64", "psx", "segacd",
    "saturn", "dreamcast", "psp", "pcengine", "arcade", "dos", "native", "windows",
]  # fmt: skip


def test_ships_required_defaults():
    assert set(REQUIRED) <= set(DEFAULT_SYSTEMS)
    for key in ("dos", "native", "windows"):
        assert DEFAULT_SYSTEMS[key].kind == "bundle"
    assert DEFAULT_SYSTEMS["psx"].bios == ("scph5501.bin",)
    assert DEFAULT_SYSTEMS["snes"].core == "snes9x"


def test_saturn_and_n64_marked_variable():
    variable = {k for k, s in DEFAULT_SYSTEMS.items() if s.performance == "variable"}
    assert variable == {"saturn", "n64"}


def test_labels_fit_the_systems_pane():
    assert all(len(s.label) <= 14 for s in DEFAULT_SYSTEMS.values())


def test_extension_matching_is_case_insensitive():
    assert DEFAULT_SYSTEMS["snes"].matches("GAME.SFC")
    assert not DEFAULT_SYSTEMS["snes"].matches("game.nes")


def test_config_overrides_and_additions():
    systems = load_systems(
        {
            "psx": {"core": "swanstation", "extensions": ["chd", ".CUE"]},
            "msx": {"name": "MSX", "extensions": [".rom"], "program": "retroarch"},
        }
    )
    assert systems["psx"].core == "swanstation"
    assert systems["psx"].name == "PlayStation"  # untouched fields kept
    assert systems["psx"].extensions == (".chd", ".cue")
    assert systems["msx"].kind == "rom" and systems["msx"].label == "MSX"


def test_bad_config_entries_are_skipped(caplog):
    systems = load_systems(
        {
            "snes": {"launcher": "magic"},
            "nameless": {"extensions": [".x"]},
            "typo": "not a table",
            "nes": {"extensions": "nes"},
        }
    )
    assert systems["snes"] == DEFAULT_SYSTEMS["snes"]
    assert systems["nes"] == DEFAULT_SYSTEMS["nes"]
    assert "nameless" not in systems and "typo" not in systems
    assert len(caplog.records) == 4
