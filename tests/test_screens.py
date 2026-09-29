from datetime import datetime

import pygame
import pytest

from retro99.app import App
from retro99.input.actions import Action, InputEvent
from retro99.library.db import LibraryDB
from retro99.screens.base import Screen, ScreenStack
from retro99.screens.dialog import DialogScreen
from retro99.screens.library import LibraryScreen
from retro99.screens.palette import PaletteScreen
from retro99.screens.progress import ProgressScreen


def make_app(config, font, *, scan=True):
    app = App(config, font=font, clock=lambda: datetime(2026, 1, 1, 12, 18))
    screen = LibraryScreen()
    app.stack.push(screen)
    if scan:
        screen.start_scan(manual=False)
        app.worker.wait()
    app.render(0.0)
    return app, screen


@pytest.fixture
def app(library_config, tiny_font):
    a, _ = make_app(library_config, tiny_font)
    yield a
    a.close()


def press(app, *events):
    for e in events:
        app.dispatch(e if isinstance(e, InputEvent) else InputEvent(e))
    app.worker.wait()
    app.render(0.0)


def select_entry(app, label):
    screen = app.stack.top
    index = [e.label for e in screen.entries].index(label)
    screen.systems_list.select(index)
    app.render(0.0)


class Opaque(Screen):
    def draw(self, grid, ctx):
        pass


class Overlay(Screen):
    opaque = False

    def draw(self, grid, ctx):
        pass


def test_stack_visible_starts_at_topmost_opaque():
    s = ScreenStack()
    a, b, c = Opaque(), Opaque(), Overlay()
    for x in (a, b, c):
        s.push(x)
    assert s.visible() == [b, c]
    assert s.pop() is c and s.top is b
    s.replace(a)
    assert list(s) == [a, a]


def test_library_lists_filters_and_systems_with_games(app):
    screen = app.stack.top
    labels = [e.label for e in screen.entries]
    assert labels[:3] == ["All Games", "Favorites", "Recent"]
    assert {"DOS", "Windows", "Native Ports", "SNES", "PlayStation", "NES", "N64"} <= set(labels)
    assert "Genesis" not in labels  # no games -> not listed
    text = app.grid.text()
    for label in ("Systems", "Games", "Details", "Duke Nukem 3D", "F5", "12:18"):
        assert label in text


def test_bad_manifest_has_red_marker_and_details(app):
    select_entry(app, "DOS")
    screen = app.stack.top
    titles = [g.title for g in screen.games]
    screen.games_list.select(titles.index("broken-syntax"))
    app.render(0.0)
    row = next(y for y in range(25) if "broken-syntax" in app.grid.row_text(y))
    x = app.grid.row_text(row).index("[!]")
    assert app.grid.cell(x, row)[1] == 12  # light red
    assert "Problem" in app.grid.text()
    press(app, Action.SELECT)
    assert isinstance(app.stack.top, DialogScreen)
    assert "can't start" in app.grid.text()


def test_details_show_metadata_and_performance_note(app):
    select_entry(app, "N64")
    text = app.grid.text()
    assert "Fake Racer 64" in text and "Europe" in text
    assert "Performance varies" in text


def test_switching_systems_and_letter_jump(app):
    select_entry(app, "SNES")
    screen = app.stack.top
    assert [g.title for g in screen.games] == ["The Legend of Fakeland", "Super Fake Quest"]
    press(app, InputEvent.key("s"))
    assert screen.current_game().title == "Super Fake Quest"


def test_favorite_toggle_updates_list_and_filter(app, library_config):
    select_entry(app, "NES")
    press(app, InputEvent.fkey(2))
    assert "♥" in app.grid.text()
    select_entry(app, "Favorites")
    titles = [g.title for g in app.stack.top.games]
    assert titles == ["StarCraft", "Tiny Game Deluxe"]


def test_recent_filter_empty_text(app):
    select_entry(app, "Recent")
    assert "Nothing played yet" in app.grid.text()


def test_manual_rescan_shows_progress_then_summary(app, library_root):
    (library_root / "games/roms/snes/New Game (USA).sfc").write_bytes(b"x")
    app.dispatch(InputEvent.fkey(5))
    assert isinstance(app.stack.top, ProgressScreen)
    app.render(0.0)
    app.worker.wait()
    app.render(0.0)
    assert isinstance(app.stack.top, DialogScreen)
    assert "1 added" in app.grid.text()
    press(app, Action.SELECT)
    select_entry(app, "SNES")
    assert "New Game" in [g.title for g in app.stack.top.games]


def test_empty_library_shows_hint(tmp_path, tiny_font):
    from retro99.config import parse_config, set_data_root

    cfg = parse_config({}, dev=True)
    set_data_root(cfg, tmp_path / "empty")
    app, _ = make_app(cfg, tiny_font)
    try:
        assert "No games found" in app.grid.text()
        assert isinstance(app.stack.top, LibraryScreen)  # automatic scans don't nag
        assert "then press" in app.grid.text()
        press(app, InputEvent.fkey(5))
        assert "games folder not found" in app.grid.text()
    finally:
        app.close()


def test_box_art_overlay(library_config, library_root, tiny_font):
    media = library_config.paths.media_dir / "duke3d"
    media.mkdir(parents=True)
    cover = pygame.Surface((60, 80))
    cover.fill((255, 255, 85))  # palette yellow
    pygame.image.save(cover, str(media / "cover.png"))
    app, screen = make_app(library_config, tiny_font)
    try:
        select_entry(app, "DOS")
        screen.games_list.select([g.id for g in screen.games].index("duke3d"))
        screen.update(0, app.ctx)
        app.worker.wait()
        frame = app.render(0.0)
        ((surface, x, y),) = screen.overlays(app.ctx)
        assert surface.get_size() == (84, 112)
        assert frame.get_at((x + 40, y + 50))[:3] == (255, 255, 85)
        # a dialog on top hides the art
        press(app, InputEvent.fkey(3))
        assert app.stack.top.overlays(app.ctx) == []
    finally:
        app.close()


def test_esc_opens_menu_and_palette_screen_round_trip(app):
    press(app, Action.BACK)
    assert "Launch game" in app.grid.text()
    press(app, InputEvent.key("o", alt=True), InputEvent.key("p"))
    assert isinstance(app.stack.top, PaletteScreen)
    press(app, *[InputEvent.key(c) for c in "DIR"])
    assert "DIR" in app.grid.text() and app.grid.cursor is not None
    press(app, Action.BACK)
    assert isinstance(app.stack.top, LibraryScreen)


def test_systems_menu_selects_a_system(app):
    press(app, InputEvent.key("s", alt=True))
    labels = [i.label for i in app.stack.top.menubar.menus[1].items if not i.separator]
    press(app, *[InputEvent(Action.DOWN)] * labels.index("SNES"), Action.SELECT)
    assert app.stack.top.current_entry().label == "SNES"


def test_crt_toggle_via_menu(app):
    assert app.crt.enabled is False
    press(app, InputEvent.key("o", alt=True), InputEvent.key("c"))
    assert app.crt.enabled is True


def test_quit_needs_confirmation(app):
    press(app, InputEvent.key("x", alt=True))
    assert not app.stack.quit_requested
    press(app, Action.SELECT)  # default button is "No"
    assert not app.stack.quit_requested
    press(app, InputEvent.key("x", alt=True), InputEvent.key("y"))
    assert app.stack.quit_requested


def test_scan_on_start_uses_existing_index_in_background(library_config, tiny_font):
    with LibraryDB(library_config.paths.db) as db:
        from retro99.library.scanner import scan_library

        db.sync(scan_library(library_config.paths.games_dir, library_config.systems).games)
    library_config.library.scan_on_start = True
    app = App(library_config, font=tiny_font)
    try:
        app.stack.push(LibraryScreen())
        assert isinstance(app.stack.top, LibraryScreen)  # no modal progress
        app.render(0.0)
        assert "Scanning" in app.grid.row_text(24)
        app.worker.wait()
        app.render(0.0)
        assert "Scanning" not in app.grid.row_text(24)
    finally:
        app.close()
