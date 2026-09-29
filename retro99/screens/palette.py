"""Palette and font test: the 16 colors, the full CP437 chart, and an input field
to check the blinking block cursor."""

from __future__ import annotations

from retro99.input.actions import Action, InputEvent
from retro99.render.font import CP437
from retro99.render.palette import Color, display_name
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import DOUBLE, SINGLE, Rect, TextInput, draw_box
from retro99.screens.base import AppContext, Screen


class PaletteScreen(Screen):
    """The 16 colors, the full CP437 chart, and an input field to test the cursor."""

    def __init__(self) -> None:
        self.input = TextInput(max_len=60)

    def handle(self, ev: InputEvent, ctx: AppContext) -> None:
        if ev.action is Action.BACK:
            ctx.stack.pop()
        else:
            self.input.handle(ev)

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        t = ctx.theme
        grid.clear(t.desktop_fg, t.desktop_bg)
        frame = Rect(0, 0, grid.cols, grid.rows)
        draw_box(
            grid,
            frame,
            DOUBLE,
            t.pane_border,
            t.pane_bg,
            title="Palette & Font Test",
            title_fg=t.pane_title_fg,
        )

        colors = Rect(2, 2, 26, 18)
        draw_box(grid, colors, SINGLE, Color.LIGHT_GRAY, Color.BLACK, title="Colors")
        for c in Color:
            y = colors.y + 1 + c
            grid.fill(colors.x + 2, y, 4, 1, " ", bg=c)
            grid.write(colors.x + 7, y, f"{c:2d} {display_name(c)}", Color.LIGHT_GRAY, Color.BLACK)

        chart = Rect(31, 2, 37, 19)
        draw_box(grid, chart, SINGLE, t.pane_fg, t.pane_bg, title="Code Page 437")
        hexdigits = "0123456789ABCDEF"
        for i, d in enumerate(hexdigits):
            grid.put(chart.x + 4 + i * 2, chart.y + 1, d, t.pane_label_fg, t.pane_bg)
            grid.put(chart.x + 2, chart.y + 2 + i, d, t.pane_label_fg, t.pane_bg)
        for code, ch in enumerate(CP437):
            row, col = divmod(code, 16)
            grid.put(chart.x + 4 + col * 2, chart.y + 2 + row, ch, Color.WHITE, t.pane_bg)

        grid.write(2, 22, "Type here:", t.pane_label_fg, t.pane_bg)
        self.input.draw(grid, 13, 22, 60, t)
        grid.write(2, 23, "Esc returns to the library", t.pane_fg, t.pane_bg)
