"""The main screen: systems, games and details, backed by the SQLite index."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pygame

from retro99.config import Config
from retro99.input.actions import Action, InputEvent
from retro99.library.db import LibraryDB, SyncStats
from retro99.library.media import load_ega_art
from retro99.library.models import Game, format_play_time
from retro99.library.scanner import ScanResult, scan_library
from retro99.render.palette import Color
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import (
    DOUBLE,
    SINGLE,
    FunctionKeyBar,
    ListBox,
    ListItem,
    Menu,
    MenuBar,
    MenuItem,
    Rect,
    draw_box,
    draw_title,
    draw_vdivider,
    fit,
    separator,
    wrap,
)
from retro99.screens.base import AppContext, Overlay, Screen
from retro99.screens.dialog import confirm, message
from retro99.screens.palette import PaletteScreen
from retro99.screens.progress import Progress, ProgressScreen

log = logging.getLogger(__name__)

HELP_TEXT = (
    "Arrows      move\n"
    "Tab         switch pane\n"
    "Enter       launch / open\n"
    "Esc / F10   menu\n"
    "A-Z         jump to title\n"
    "F2          toggle favorite\n"
    "F3          game info\n"
    "F5          rescan library\n"
    "Alt-X       quit"
)

# Layout of the 80x25 main screen.
FRAME = Rect(0, 1, 80, 23)
SYSTEMS_X, DETAILS_X = 17, 56
ART_ROWS = 9  # art box height in rows, including its border

FILTERS = (("all", "All Games"), ("favorites", "Favorites"), ("recent", "Recent"))


@dataclass(frozen=True)
class Entry:
    """One row of the systems pane: a filter or a system."""

    kind: str  # "filter" | "system"
    key: str
    label: str


def run_scan(report, config: Config) -> tuple[ScanResult, SyncStats]:
    """Worker-thread job: scan the games folders and sync the index."""
    result = scan_library(config.paths.games_dir, config.systems, lambda d, t, c: report((d, t, c)))
    with LibraryDB(config.paths.db) as db:
        stats = db.sync(result.games)
    return result, stats


class LibraryScreen(Screen):
    def __init__(self) -> None:
        self.entries: list[Entry] = []
        self.games: list[Game] = []
        self.focus = 1  # 0 = systems, 1 = games
        self.systems_list = ListBox(on_change=lambda _: self._load_games())
        self.games_list = ListBox(on_activate=lambda _: self._launch())
        self.fkeys = FunctionKeyBar(
            [("F1", "Help"), ("F2", "Fav"), ("F3", "Info"), ("F5", "Rescan"), ("F10", "Menu")]
        )
        self.menubar: MenuBar | None = None
        self.scan: Progress | None = None
        self._scan_screen: ProgressScreen | None = None
        self.art: dict[str, pygame.Surface | None] = {}
        self._art_pending: set[str] = set()
        self._ctx: AppContext | None = None
        self._started = False

    # ------------------------------------------------------------------ data
    @property
    def ctx(self) -> AppContext:
        assert self._ctx is not None
        return self._ctx

    @property
    def db(self) -> LibraryDB:
        assert self.ctx.db is not None
        return self.ctx.db

    def current_entry(self) -> Entry | None:
        if not self.entries:
            return None
        return self.entries[self.systems_list.selected]

    def current_game(self) -> Game | None:
        return self.games[self.games_list.selected] if self.games else None

    def refresh(self) -> None:
        """Reload the systems pane and game list from the database, keeping the selection."""
        entry, game = self.current_entry(), self.current_game()
        counts = self.db.system_counts()
        systems = self.ctx.config.systems
        entries = [Entry("filter", key, label) for key, label in FILTERS]
        entries += [Entry("system", k, s.label) for k, s in systems.items() if counts.get(k)]
        entries += [Entry("system", k, k) for k in sorted(counts) if k not in systems]
        self.entries = entries
        items = []
        for e in entries:
            n = counts.get(e.key, 0) if e.kind == "system" else None
            if e.key == "all":
                n = sum(counts.values())
            items.append(ListItem(e.label, suffix=str(n) if n else ""))
        index = next((i for i, e in enumerate(entries) if e == entry), 0)
        self.systems_list.set_items(items, index)
        self._load_games(keep_id=game.id if game else None)
        if self.menubar is not None:
            self.menubar.menus[1].items = self._systems_menu_items()

    def _load_games(self, keep_id: str | None = None) -> None:
        entry = self.current_entry()
        if entry is None:
            self.games = []
        elif entry.kind == "system":
            self.games = self.db.games_for(entry.key)
        elif entry.key == "favorites":
            self.games = self.db.favorites()
        elif entry.key == "recent":
            self.games = self.db.recent()
        else:
            self.games = self.db.all_games()
        self.games_list.empty_text = self._empty_text(entry)
        index = next((i for i, g in enumerate(self.games) if g.id == keep_id), 0)
        self.games_list.set_items([self._game_item(g) for g in self.games], index)

    def _empty_text(self, entry: Entry | None) -> str:
        if self.scan is not None:
            return "Scanning..."
        if entry is not None and entry.key == "favorites":
            return "No favorites yet (F2)"
        if entry is not None and entry.key == "recent":
            return "Nothing played yet"
        return "No games found"

    @staticmethod
    def _game_item(g: Game) -> ListItem:
        year = str(g.year) if g.year else "    "
        return ListItem(
            g.title,
            prefix="[!]" if g.error else "",
            prefix_fg=Color.LIGHT_RED,
            suffix=f"{year} {'♥' if g.favorite else ' '}",
        )

    # --------------------------------------------------------------- scanning
    def start_scan(self, *, manual: bool, modal: bool = True) -> None:
        if self.scan is not None or self.ctx.worker is None:
            return
        progress = Progress()
        self.scan = progress
        if modal:
            self._scan_screen = ProgressScreen("Rescan", progress, "Reading the games folders...")
            self.ctx.stack.push(self._scan_screen)

        def on_progress(p: tuple[int, int, str]) -> None:
            progress.done, progress.total, progress.current = p

        def finish() -> None:
            self.scan = None
            if self._scan_screen is not None and self.ctx.stack.top is self._scan_screen:
                self.ctx.stack.pop()
            self._scan_screen = None

        def on_done(value: tuple[ScanResult, SyncStats]) -> None:
            finish()
            self.refresh()
            result, stats = value
            if manual:  # automatic scans stay quiet; warnings go to the log
                self.ctx.stack.push(message("Rescan", self._scan_summary(result, stats)))

        def on_error(e: BaseException) -> None:
            finish()
            self.ctx.stack.push(message("Rescan", f"The scan failed:\n{e}", error=True))

        self.ctx.worker.submit(
            run_scan,
            self.ctx.config,
            on_done=on_done,
            on_error=on_error,
            on_progress=on_progress,
            name="scan",
        )

    @staticmethod
    def _scan_summary(result: ScanResult, stats: SyncStats) -> str:
        lines = [f"{len(result.games)} games in the library."]
        if stats.added or stats.removed:
            lines.append(f"{stats.added} added, {stats.removed} removed.")
        if result.errors:
            lines.append(f"{len(result.errors)} with problems, marked [!].")
        lines.extend(result.warnings[:4])
        return "\n".join(lines)

    # -------------------------------------------------------------------- art
    def _art_box(self) -> Rect:
        top = FRAME.y + 1
        return Rect(DETAILS_X + 2, top, FRAME.right - DETAILS_X - 3, ART_ROWS)

    def _art_pixels(self) -> tuple[int, int]:
        cw, ch = self.ctx.cell_size
        box = self._art_box()
        return (box.w - 2) * cw, (box.h - 2) * ch

    def _request_art(self, game: Game) -> None:
        if game.id in self.art or game.id in self._art_pending or self.ctx.worker is None:
            return
        self._art_pending.add(game.id)
        media_dir = self.ctx.config.paths.media_dir
        size = self._art_pixels()

        def done(surface: pygame.Surface | None, game_id: str = game.id) -> None:
            self._art_pending.discard(game_id)
            self.art[game_id] = surface

        def failed(_: BaseException, game_id: str = game.id) -> None:
            done(None, game_id)

        self.ctx.worker.submit(
            lambda _report: load_ega_art(media_dir, game.id, size),
            on_done=done,
            on_error=failed,
            name=f"art:{game.id}",
        )

    def overlays(self, ctx: AppContext) -> list[Overlay]:
        game = self.current_game()
        surface = self.art.get(game.id) if game else None
        if surface is None or (self.menubar is not None and self.menubar.is_open):
            return []
        cw, ch = ctx.cell_size
        box = self._art_box()
        w, h = self._art_pixels()
        x = (box.x + 1) * cw + (w - surface.get_width()) // 2
        y = (box.y + 1) * ch + (h - surface.get_height()) // 2
        return [(surface, x, y)]

    # ---------------------------------------------------------------- actions
    def _launch(self) -> None:
        game = self.current_game()
        if game is None:
            return
        if game.error:
            self.ctx.stack.push(
                message(game.title, f"This game can't start:\n\n{game.error}", error=True)
            )
            return
        self.ctx.stack.push(
            message(
                "Launch",
                f"{game.title} would start with {game.program or game.launcher}.\n\n"
                "Launching is wired up in Phase 3.",
            )
        )

    def _info(self) -> None:
        game = self.current_game()
        if game is None:
            return
        system = self.ctx.config.systems.get(game.system)
        lines = [
            f"ID: {game.id}",
            f"System: {system.name if system else game.system}",
            f"Launcher: {game.launcher or '-'} ({game.program or '-'})",
            f"Path: {game.path}",
        ]
        if game.notes:
            lines += ["", game.notes]
        if game.error:
            lines += ["", f"Problem: {game.error}"]
        self.ctx.stack.push(message(game.title, "\n".join(lines), error=bool(game.error)))

    def _toggle_favorite(self) -> None:
        game = self.current_game()
        if game is None:
            return
        self.db.set_favorite(game, not game.favorite)
        self.refresh()  # counts and the Favorites filter change too

    def _rescan(self) -> None:
        self.start_scan(manual=True)

    def _select_entry(self, index: int) -> None:
        self.systems_list.select(index)
        self.focus = 1

    def _systems_menu_items(self) -> list[MenuItem]:
        items = []
        for i, e in enumerate(self.entries):
            if i == len(FILTERS):
                items.append(separator())
            items.append(MenuItem(e.label, lambda i=i: self._select_entry(i)))
        return items

    def _toggle_crt(self) -> None:
        self.ctx.crt.enabled = not self.ctx.crt.enabled

    def _quit(self) -> None:
        self.ctx.stack.push(confirm("Quit", "Quit RETRO-99?", self.ctx.stack.quit))

    def _build_menu(self) -> MenuBar:
        ctx = self.ctx
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
                Menu("&Systems", self._systems_menu_items()),
                Menu(
                    "&Options",
                    [
                        MenuItem(
                            "&CRT scanlines", self._toggle_crt, checked=lambda: ctx.crt.enabled
                        ),
                        MenuItem("&Palette and font test", lambda: ctx.stack.push(PaletteScreen())),
                    ],
                ),
                Menu(
                    "&Help",
                    [
                        MenuItem("&Keys", lambda: ctx.stack.push(message("Help", HELP_TEXT)), "F1"),
                        MenuItem(
                            "&About RETRO-99",
                            lambda: ctx.stack.push(
                                message(
                                    "About",
                                    "RETRO-99 game launcher\n\nRaspberry Pi 5 in a TI-99/4A case.",
                                )
                            ),
                        ),
                    ],
                ),
            ]
        )

    # ------------------------------------------------------------- screen API
    def on_enter(self, ctx: AppContext) -> None:
        self._ctx = ctx
        if self._started:
            return
        self._started = True
        self.menubar = self._build_menu()
        self.refresh()
        if ctx.config.library.scan_on_start or self.db.count() == 0:
            # With an empty index there is nothing to show, so make the scan visible.
            self.start_scan(manual=False, modal=self.db.count() == 0)

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
            actions = {
                1: lambda: ctx.stack.push(message("Help", HELP_TEXT)),
                2: self._toggle_favorite,
                3: self._info,
                5: self._rescan,
            }
            actions.get(ev.number, lambda: None)()
        elif a is Action.CHAR and ev.alt and ev.char.lower() == "x":
            self._quit()
        elif self.focus == 0:
            if a is Action.SELECT:
                self.focus = 1
            else:
                self.systems_list.handle(ev)
        else:
            self.games_list.handle(ev)

    def update(self, dt: float, ctx: AppContext) -> None:
        game = self.current_game()
        if game is not None:
            self._request_art(game)

    def draw(self, grid: TextGrid, ctx: AppContext) -> None:
        self._ctx = ctx
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
        self.systems_list.draw(grid, Rect(1, top, SYSTEMS_X - 1, h), t, focused=self.focus == 0)
        self.games_list.draw(
            grid,
            Rect(SYSTEMS_X + 1, top, DETAILS_X - SYSTEMS_X - 1, h),
            t,
            focused=self.focus == 1,
        )
        self._draw_details(grid, Rect(DETAILS_X + 1, top, FRAME.right - DETAILS_X - 1, h))

        self.fkeys.draw(grid, t)
        if self.scan is not None:
            status = f" Scanning {self.scan.done}/{self.scan.total} "
            grid.write(grid.cols - len(status), grid.rows - 1, status, Color.YELLOW, Color.BLACK)
        assert self.menubar is not None
        self.menubar.draw(grid, t, ctx.clock().strftime("%H:%M"))

    def _draw_details(self, grid: TextGrid, rect: Rect) -> None:
        t = self.ctx.theme
        game = self.current_game()
        if game is None:
            if self.db.count() == 0 and self.scan is None:
                hint = f"Put games in {self.ctx.config.paths.games_dir}, then press F5."
                for i, line in enumerate(wrap(hint, rect.w - 2)[: rect.h]):
                    grid.write(rect.x + 1, rect.y + i, line, t.pane_fg, t.pane_bg)
            return

        art = self._art_box()
        draw_box(grid, art, SINGLE, t.pane_fg, t.pane_bg)
        if self.art.get(game.id) is None:
            grid.fill(art.x + 1, art.y + 1, art.w - 2, art.h - 2, "░", Color.CYAN, t.pane_bg)
            label = " LOADING " if game.id in self._art_pending else " NO ART "
            grid.write(art.x + (art.w - len(label)) // 2, art.y + art.h // 2, label,
                       t.pane_label_fg, t.pane_bg)  # fmt: skip

        y = art.bottom + 1
        bottom = rect.bottom
        width = rect.w - 2
        for line in wrap(game.title, width)[:2]:
            grid.write(rect.x + 1, y, line, Color.WHITE, t.pane_bg)
            y += 1

        def row(label: str, value: str, fg: int = t.pane_fg) -> None:
            nonlocal y
            if y > bottom or not value:
                return
            grid.write(rect.x + 1, y, f"{label}:", t.pane_label_fg, t.pane_bg)
            value_x = rect.x + 12
            if len(value) > rect.right - value_x + 1:
                # Too long for the value column: give it its own indented line.
                y += 1
                value_x = rect.x + 3
            if y <= bottom:
                grid.write(value_x, y, fit(value, rect.right - value_x + 1).rstrip(), fg, t.pane_bg)
            y += 1

        if game.error:
            y += 1
            grid.write(rect.x + 1, y, "[!] Problem:", Color.LIGHT_RED, t.pane_bg)
            y += 1
            for line in wrap(game.error, width):
                if y > bottom:
                    break
                grid.write(rect.x + 1, y, line, Color.LIGHT_RED, t.pane_bg)
                y += 1
            return

        system = self.ctx.config.systems.get(game.system)
        row("Year", str(game.year) if game.year else "")
        row("Publisher", game.publisher)
        row("Genre", game.genre)
        row("Players", game.players)
        row("System", system.label if system else game.system)
        row("Region", game.region)
        row("Played", format_play_time(game.play_seconds))
        row("Last", game.last_played.strftime("%Y-%m-%d") if game.last_played else "never")
        if game.favorite:
            row("Favorite", "♥ yes", Color.LIGHT_RED)
        if system is not None and system.performance == "variable" and y <= bottom:
            for line in wrap("Performance varies on the Pi.", width):
                if y <= bottom:
                    grid.write(rect.x + 1, y, line, Color.YELLOW, t.pane_bg)
                    y += 1
