"""Headless smoke test: real App.run with SDL's dummy video driver."""

import pygame

from retro99.__main__ import main
from retro99.app import App
from retro99.config import parse_config
from retro99.screens.demo import DemoScreen, PaletteScreen


def test_every_screen_renders_through_the_real_loop(tiny_font):
    for screen in (DemoScreen(), PaletteScreen()):
        app = App(parse_config({}, dev=True), font=tiny_font)
        assert app.run(screen, max_frames=3) == 0
        assert not pygame.display.get_init()  # display released on exit


def test_keyboard_events_flow_through_the_loop(tiny_font):
    app = App(parse_config({}, dev=True), font=tiny_font)
    pygame.init()
    app.display.open()
    try:
        app.stack.push(DemoScreen())
        for key in (pygame.K_F10, pygame.K_ESCAPE, pygame.K_RETURN):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
        app._pump_events()
        app.display.present(app.render(0.0))
        assert type(app.stack.top).__name__ == "DialogScreen"
        # Release and re-acquire the display, as the launcher will around a game.
        app.display.close()
        app.display.open()
        app.renderer.invalidate()
        app.display.present(app.render(0.0))
    finally:
        app.display.close()
        pygame.quit()


def test_cli_entry_point_headless():
    assert main(["--headless", "--windowed", "--frames", "2"]) == 0
