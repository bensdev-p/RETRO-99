"""Phase 1 demo: the three-pane library layout with placeholder data, plus a
palette/font test screen. Replaced by the real library screen in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass

from retro99.input.actions import Action, InputEvent
from retro99.render.font import CP437
from retro99.render.palette import Color, display_name
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import (
    DOUBLE,
    SINGLE,
    FunctionKeyBar,
    ListBox,
    Menu,
    MenuBar,
    MenuItem,
    Rect,
    TextInput,
    draw_box,
    draw_title,
    draw_vdivider,
    fit,
    separator,
    wrap,
)
from retro99.screens.base import AppContext, Screen
from retro99.screens.dialog import confirm, message


@dataclass
class DemoGame:
    title: str
    year: int
    publisher: str
    genre: str
    launcher: str
    program: str
    players: str = "1"
    favorite: bool = False


def demo_library() -> dict[str, list[DemoGame]]:
    return {
        "DOS": [
            DemoGame("Duke Nukem 3D", 1996, "3D Realms", "FPS", "native", "eduke32"),
            DemoGame(
                "SODA Off-Road Racing", 1997, "Sierra", "Racing", "emulator", "dosbox-staging"
            ),
        ],
        "Native": [
            DemoGame("Half-Life", 1998, "Valve", "FPS", "native", "xash3d"),
        ],
        "Windows": [
            DemoGame("StarCraft", 1998, "Blizzard", "RTS", "wine", "wine", players="1-8"),
        ],
        "SNES": [],
        "PlayStation": [],
    }


HELP_TEXT = (
    "Arrows      move\n"
    "Tab         switch pane\n"
    "Enter       launch / open\n"
    "Esc / F10   menu\n"
    "A-Z         jump to title\n"
    "F2          toggle favorite\n"
    "F3          game info\n"
    "Alt-X       quit"
)

# Layout of the 80x25 main screen.
FRAME = Rect(0, 1, 80, 23)
SYSTEMS_X, DETAILS_X = 17, 56


class DemoScreen(Screen):
    def __init__(self) -> None:
        self.library = demo_library()
        self.system_names = list(self.library)
        self.focus = 1  # 0 = systems, 1 = games
        self.systems = ListBox(self.system_names, on_change=lambda _: self._load_games())
        self.games = ListBox(empty_text="No games", on_activate=lambda _: self._launch())
        self.fkeys = FunctionKeyBar(
            [("F1", "Help"), ("F2", "Fav"), ("F3", "Info"), ("F5", "Rescan"), ("F10", "Menu")]
        )
        self.menubar: MenuBar | None = None
        self._ctx: AppContext | None = None
        self._load_games()

    # data -------------------------------------------------------------------
    def _current_games(self) -> list[DemoGame]:
        return self.library[self.system_names[self.systems.selected]]

    def _current_game(self) -> DemoGame | None:
        games = self._current_games()
        return games[self.games.selected] if games else None

    def _game_line(self, g: DemoGame, width: int) -> str:
        mark = "♥" if g.favorite else " "
        return f"{fit(g.title, width - 7)} {g.year} {mark}"

    def _load_games(self, keep: int = 0) -> None:
        # Pane interior, minus the selection marker and a scrollbar column.
        width = DETAILS_X - SYSTEMS_X - 1 - 2
        self.games.set_items([self._game_line(g, width) for g in self._current_games()], keep)

    # actions ----------------------------------------------------------------
    def _build_menu(self, ctx: AppContext) -> MenuBar:
        def pick_system(i: int):
            def go() -> None:
                self.systems.select(i)
                self.focus = 1

            return go

        return MenuBar(
            [
                Menu(
                    "&File",
                    [
                        MenuItem("&Launch game", self._launch, "Enter"),
                        MenuItem("&Info", self._info, "F3"),
                        MenuItem("&Favorite", self._toggle_favorite, "F2"),
                        MenuItem("&Rescan library", self._rescan, "F5"),
                        separator(),
                        MenuItem("E&xit to DOS", None, enabled=False),
                        MenuItem("&Quit", self._quit, "Alt-X"),
                    ],
                ),
                Menu(
                    "&Systems",
                    [
                        MenuItem(f"&{name}", pick_system(i))
                        for i, name in enumerate(self.system_names)
                    ],
                ),
                Menu(
                    "&Options",
                    [
                        MenuItem(
                            "&CRT scanlines", self._toggle_crt, checked=lambda: ctx.crt.enabled
                        ),
                        MenuItem("&Palette and font test", self._palette),
                    ],
                ),
                Menu(
                    "&Help",
                    [
                        MenuItem("&Keys", self._help, "F1"),
                        MenuItem("&About RETRO-99", self._about),
                    ],
                ),
            ]
        )

    def _launch(self) -> None:
        game = self._current_game()
        if game is None or self._ctx is None:
            return
        self._ctx.stack.push(
            message(
                "Launch",
                f"{game.title} would start with {game.program} ({game.launcher}).\n\n"
                "Launching is wired up in Phase 3.",
            )
        )

    def _info(self) -> None:
        game = self._current_game()
        if game is None or self._ctx is None:
            return
        self._ctx.stack.push(
            message(
                game.title,
                f"Year: {game.year}\nPublisher: {game.publisher}\nGenre: {game.genre}\n"
                f"Players: {game.players}\nLauncher: {game.launcher} ({game.program})",
            )
        )

    def _toggle_favorite(self) -> None:
        game = self._current_game()
        if game is not None:
            game.favorite = not game.favorite
            self._load_games(self.games.selected)

    def _rescan(self) -> None:
        if self._ctx is not None:
            self._ctx.stack.push(message("Rescan", "The library scanner arrives in Phase 2."))

    def _toggle_crt(self) -> None:
        if self._ctx is not None:
            self._ctx.crt.enabled = not self._ctx.crt.enabled

    def _palette(self) -> None:
        if self._ctx is not None:
            self._ctx.stack.push(PaletteScreen())

    def _help(self) -> None:
        if self._ctx is not None:
            self._ctx.stack.push(message("Help", HELP_TEXT))

    def _about(self) -> None:
        if self._ctx is not None:
            self._ctx.stack.push(
                message(
                    "About",
                    "RETRO-99 game launcher\nPhase 1: renderer demo\n\n"
                    "Raspberry Pi 5 in a TI-99/4A case.",
                )
            )

    def _quit(self) -> None:
        if self._ctx is not None:
            self._ctx.stack.push(confirm("Quit", "Quit RETRO-99?", self._ctx.stack.quit))

    # screen API -------------------------------------------------------------
    def on_enter(self, ctx: AppContext) -> None:
        self._ctx = ctx
        if self.menubar is None:
            self.menubar = self._build_menu(ctx)

    def handle(self, ev: InputEvent, ctx: AppContext) -> None:
        self._ctx = ctx
        assert self.menubar is not None
        if self.menubar.handle(ev):
            return
        a = ev.action
        if a is Action.BACK:
            self.menubar.open(0)  # Esc at the root opens the menu (the TI has no F10)
        elif a is Action.TAB:
            self.focus = 1 - self.focus
        elif a is Action.LEFT:
            self.focus = 0
        elif a is Action.RIGHT:
            self.focus = 1
        elif a is Action.FUNCTION:
            {1: self._help, 2: self._toggle_favorite, 3: self._info, 5: self._rescan}.get(
                ev.number, lambda: None
            )()
        elif a is Action.CHAR and ev.alt and ev.char.lower() == "x":
            self._quit()
        elif self.focus == 0:
            if a is Action.SELECT:
                self.focus = 1
            else:
                self.systems.handle(ev)
        else:
            self.games.handle(ev)

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        t = ctx.theme
        grid.clear(t.desktop_fg, t.desktop_bg)
        draw_box(grid, FRAME, DOUBLE, t.pane_border, t.pane_bg)
        draw_vdivider(grid, SYSTEMS_X, FRAME.y, FRAME.bottom, DOUBLE, t.pane_border, t.pane_bg)
        draw_vdivider(grid, DETAILS_X, FRAME.y, FRAME.bottom, DOUBLE, t.pane_border, t.pane_bg)

        panes = [
            ("Systems", Rect(FRAME.x, FRAME.y, SYSTEMS_X + 1, FRAME.h), 0),
            ("Games", Rect(SYSTEMS_X, FRAME.y, DETAILS_X - SYSTEMS_X + 1, FRAME.h), 1),
            ("Details", Rect(DETAILS_X, FRAME.y, FRAME.right - DETAILS_X + 1, FRAME.h), 2),
        ]
        for title, rect, index in panes:
            focused = index == self.focus
            fg = t.pane_title_focus_fg if focused else t.pane_title_fg
            bg = t.pane_title_focus_bg if focused else t.pane_bg
            draw_title(grid, rect, title, fg, bg, align="left")

        top, h = FRAME.y + 1, FRAME.h - 2
        self.systems.draw(grid, Rect(1, top, SYSTEMS_X - 1, h), t, focused=self.focus == 0)
        self.games.draw(
            grid, Rect(SYSTEMS_X + 1, top, DETAILS_X - SYSTEMS_X - 1, h), t, focused=self.focus == 1
        )
        self._draw_details(grid, Rect(DETAILS_X + 1, top, FRAME.right - DETAILS_X - 1, h), ctx)

        self.fkeys.draw(grid, t)
        assert self.menubar is not None
        self.menubar.draw(grid, t, ctx.clock().strftime("%H:%M"))

    def _draw_details(self, grid: TextGrid, rect: Rect, ctx: AppContext) -> None:
        t = ctx.theme
        game = self._current_game()
        if game is None:
            grid.write(rect.x + 1, rect.y, "Nothing selected", t.pane_fg, t.pane_bg)
            return
        art = Rect(rect.x + 1, rect.y, rect.w - 2, 8)
        draw_box(grid, art, SINGLE, t.pane_fg, t.pane_bg)
        grid.fill(art.x + 1, art.y + 1, art.w - 2, art.h - 2, "░", Color.CYAN, t.pane_bg)
        grid.write(
            art.x + (art.w - 8) // 2, art.y + art.h // 2 - 1, " NO ART ", t.pane_label_fg, t.pane_bg
        )
        y = art.bottom + 2
        fields = [
            ("Year", str(game.year)),
            ("Publisher", game.publisher),
            ("Genre", game.genre),
            ("Players", game.players),
            ("Launcher", game.launcher),
            ("Played", "never"),
        ]
        for label, value in fields:
            if y > rect.bottom:
                break
            grid.write(rect.x + 1, y, f"{label}:", t.pane_label_fg, t.pane_bg)
            for line in wrap(value, rect.w - 12)[:2]:
                grid.write(rect.x + 12, y, line, t.pane_fg, t.pane_bg)
                y += 1
        if game.favorite and y + 1 <= rect.bottom:
            grid.write(rect.x + 1, y + 1, "♥ Favorite", Color.LIGHT_RED, t.pane_bg)


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
