"""The main loop and screen stack. The only place that owns long-lived state."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime

import pygame

from retro99.config import Config
from retro99.input.actions import InputEvent
from retro99.input.keyboard import translate
from retro99.library.db import LibraryDB
from retro99.render.crt import CrtEffect
from retro99.render.display import Display
from retro99.render.font import BitmapFont, load_font
from retro99.render.textgrid import COLS, ROWS, GridRenderer, TextGrid
from retro99.screens.base import AppContext, Screen, ScreenStack
from retro99.tasks import Worker

log = logging.getLogger(__name__)

CURSOR_BLINK_SECONDS = 0.27  # roughly the VGA hardware cursor rate


class App:
    def __init__(
        self,
        config: Config,
        *,
        font: BitmapFont | None = None,
        db: LibraryDB | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.config = config
        self.font = font or load_font(config.paths.fonts)
        self.grid = TextGrid(COLS, ROWS)
        self.renderer = GridRenderer(self.font, COLS, ROWS)
        self.crt = CrtEffect(config.ui.crt, config.ui.crt_strength)
        self.display = Display(
            self.renderer.size,
            fullscreen=config.display.fullscreen,
            window_scale=config.display.window_scale,
            crt=self.crt,
        )
        self.stack = ScreenStack()
        self.worker = Worker()
        self.db = db if db is not None else LibraryDB(config.paths.db)
        self.ctx = AppContext(
            config=config,
            stack=self.stack,
            db=self.db,
            worker=self.worker,
            crt=self.crt,
            cell_size=(self.font.width, self.font.height),
            clock=clock,
        )
        self.stack.bind(self.ctx)

    def dispatch(self, ev: InputEvent) -> None:
        top = self.stack.top
        if top is not None:
            top.handle(ev, self.ctx)

    def render(self, now: float) -> pygame.Surface:
        self.grid.clear()
        visible = self.stack.visible()
        for screen in visible:
            screen.draw(self.grid, self.ctx)
        cursor_on = int(now / CURSOR_BLINK_SECONDS) % 2 == 0
        frame = self.renderer.render(self.grid, cursor_on)
        # Only the topmost screen's overlays are drawn, so a dialog hides the art below it.
        if visible:
            for surface, x, y in visible[-1].overlays(self.ctx):
                rect = frame.blit(surface, (x, y))
                self.renderer.invalidate_pixels(rect)
        return frame

    def close(self) -> None:
        self.worker.shutdown()
        self.db.close()

    def _pump_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.stack.quit()
            elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                self.display.resized()
            elif event.type == pygame.WINDOWEXPOSED:
                self.renderer.invalidate()
            else:
                ev = translate(event)
                if ev is not None:
                    self.dispatch(ev)

    def run(self, first: Screen, *, max_frames: int | None = None) -> int:
        """Run until a screen asks to quit or the stack empties. Returns an exit code."""
        pygame.init()
        self.display.open()
        pygame.key.set_repeat(300, 40)
        self.stack.push(first)
        clock = pygame.time.Clock()
        frames = 0
        try:
            while not self.stack.quit_requested and len(self.stack):
                self._pump_events()
                self.worker.poll()
                dt = clock.tick(self.config.display.fps) / 1000.0
                top = self.stack.top
                if top is None:
                    break
                top.update(dt, self.ctx)
                self.display.present(self.render(time.monotonic()))
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        finally:
            self.display.close()
            self.close()
            pygame.quit()
        return 0
