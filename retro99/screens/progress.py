"""A progress window for background work (library scans)."""

from __future__ import annotations

from dataclasses import dataclass

from retro99.input.actions import Action, InputEvent
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import DOUBLE, Rect, draw_box, draw_shadow, fit
from retro99.screens.base import AppContext, Screen


@dataclass
class Progress:
    done: int = 0
    total: int = 0
    current: str = ""


class ProgressScreen(Screen):
    """Shows ``progress`` until the owner pops it. Esc hides it; the work carries on."""

    opaque = False

    def __init__(self, title: str, progress: Progress, text: str = "Please wait...") -> None:
        self.title = title
        self.progress = progress
        self.text = text

    def handle(self, ev: InputEvent, ctx: AppContext) -> None:
        if ev.action is Action.BACK:
            ctx.stack.pop()

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        t = ctx.theme
        rect = Rect.centered(50, 8, grid.cols, grid.rows)
        draw_box(grid, rect, DOUBLE, t.dialog_border, t.dialog_bg, title=self.title)
        grid.recolor(rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2, t.dialog_fg, t.dialog_bg)
        inner = rect.w - 6
        p = self.progress
        grid.write(rect.x + 3, rect.y + 2, fit(self.text, inner), t.dialog_fg, t.dialog_bg)
        grid.write(rect.x + 3, rect.y + 3, fit(p.current, inner), t.dialog_fg, t.dialog_bg)
        filled = inner * p.done // p.total if p.total else 0
        grid.write(rect.x + 3, rect.y + 4, "█" * filled + "░" * (inner - filled), t.select_bg,
                   t.dialog_bg)  # fmt: skip
        count = f"{p.done} of {p.total}" if p.total else "Looking for games..."
        grid.write(rect.x + 3, rect.y + 5, fit(count, inner), t.dialog_fg, t.dialog_bg)
        draw_shadow(grid, rect, t)
