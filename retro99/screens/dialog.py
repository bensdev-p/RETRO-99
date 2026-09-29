"""A modal dialog as a screen, drawn over whatever is below it."""

from __future__ import annotations

from collections.abc import Callable

from retro99.input.actions import InputEvent
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import Dialog
from retro99.screens.base import AppContext, Screen


class DialogScreen(Screen):
    opaque = False

    def __init__(self, dialog: Dialog, on_close: Callable[[int | None], None] | None = None):
        self.dialog = dialog
        self.on_close = on_close

    def handle(self, ev: InputEvent, ctx: AppContext) -> None:
        self.dialog.handle(ev)
        if self.dialog.done:
            ctx.stack.pop()
            if self.on_close:
                self.on_close(self.dialog.result)

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        self.dialog.draw(grid, ctx.theme)


def message(title: str, text: str, *, error: bool = False) -> DialogScreen:
    return DialogScreen(Dialog(title, text, error=error))


def confirm(title: str, text: str, on_yes: Callable[[], None]) -> DialogScreen:
    def close(result: int | None) -> None:
        if result == 0:
            on_yes()

    return DialogScreen(Dialog(title, text, ("&Yes", "&No"), default=1), close)
