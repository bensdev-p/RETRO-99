"""Screen interface and the screen stack.

Screens push and pop (library -> detail -> settings); ESC / gamepad B goes back
one level. Non-opaque screens (dialogs) are drawn on top of the ones below.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from retro99.input.actions import InputEvent
from retro99.render.crt import CrtEffect
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import DEFAULT_THEME, Theme

if TYPE_CHECKING:
    from retro99.config import Config


class Screen:
    opaque: bool = True

    def on_enter(self, ctx: AppContext) -> None:
        """Called when the screen becomes the top of the stack."""

    def handle(self, ev: InputEvent, ctx: AppContext) -> None:
        """React to one input event (only the top screen receives input)."""

    def update(self, dt: float, ctx: AppContext) -> None:
        """Advance timers/animations; called once per frame for the top screen."""

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        raise NotImplementedError


class ScreenStack:
    def __init__(self) -> None:
        self._screens: list[Screen] = []
        self.quit_requested = False
        self._ctx: AppContext | None = None

    def bind(self, ctx: AppContext) -> None:
        self._ctx = ctx

    def push(self, screen: Screen) -> None:
        self._screens.append(screen)
        if self._ctx is not None:
            screen.on_enter(self._ctx)

    def pop(self) -> Screen | None:
        screen = self._screens.pop() if self._screens else None
        if self._screens and self._ctx is not None:
            self._screens[-1].on_enter(self._ctx)
        return screen

    def replace(self, screen: Screen) -> None:
        if self._screens:
            self._screens.pop()
        self.push(screen)

    def quit(self) -> None:
        self.quit_requested = True

    @property
    def top(self) -> Screen | None:
        return self._screens[-1] if self._screens else None

    def visible(self) -> list[Screen]:
        """Screens to draw, bottom first: the topmost opaque screen and everything above."""
        start = 0
        for i in range(len(self._screens) - 1, -1, -1):
            if self._screens[i].opaque:
                start = i
                break
        return self._screens[start:]

    def __len__(self) -> int:
        return len(self._screens)

    def __iter__(self) -> Iterator[Screen]:
        return iter(self._screens)


@dataclass
class AppContext:
    """Everything a screen may touch. Passed explicitly; there are no globals."""

    config: Config
    stack: ScreenStack
    crt: CrtEffect = field(default_factory=CrtEffect)
    theme: Theme = DEFAULT_THEME
    clock: Callable[[], datetime] = datetime.now
