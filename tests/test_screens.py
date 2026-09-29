from datetime import datetime

import pytest

from retro99.app import App
from retro99.config import parse_config
from retro99.input.actions import Action, InputEvent
from retro99.screens.base import Screen, ScreenStack
from retro99.screens.demo import DemoScreen, PaletteScreen
from retro99.screens.dialog import DialogScreen


@pytest.fixture
def app(tiny_font):
    a = App(parse_config({}, dev=True), font=tiny_font, clock=lambda: datetime(2026, 1, 1, 12, 18))
    a.stack.push(DemoScreen())
    return a


def press(app, *events):
    for e in events:
        app.dispatch(e if isinstance(e, InputEvent) else InputEvent(e))
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


def test_demo_renders_three_panes_menu_and_fkeys(app):
    app.render(0.0)
    text = app.grid.text()
    for label in ("Systems", "Games", "Details", "Duke Nukem 3D", "F1", "Help", "12:18"):
        assert label in text
    assert app.grid.cell(0, 1)[0] == "╔"


def test_switching_system_reloads_games(app):
    press(app, Action.LEFT, Action.DOWN, Action.DOWN)  # DOS -> Native -> Windows
    assert "StarCraft" in app.grid.text()
    press(app, Action.DOWN)  # -> SNES, empty
    assert "No games" in app.grid.text()


def test_enter_on_game_opens_dialog_and_esc_closes(app):
    press(app, Action.SELECT)
    assert isinstance(app.stack.top, DialogScreen)
    assert "Launch" in app.grid.text()
    assert "Systems" in app.grid.text()  # dialog is drawn over the library
    press(app, Action.BACK)
    assert isinstance(app.stack.top, DemoScreen)


def test_favorite_toggle_marks_list(app):
    press(app, InputEvent.fkey(2))
    assert "♥" in app.grid.row_text(2)


def test_esc_opens_menu_and_palette_screen_round_trip(app):
    press(app, Action.BACK)
    assert "Launch game" in app.grid.text()
    press(app, InputEvent.key("o", alt=True), InputEvent.key("p"))
    assert isinstance(app.stack.top, PaletteScreen)
    press(app, *[InputEvent.key(c) for c in "DIR"])
    assert "DIR" in app.grid.text() and app.grid.cursor is not None
    press(app, Action.BACK)
    assert isinstance(app.stack.top, DemoScreen)


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
