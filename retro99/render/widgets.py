"""DOS-style widgets drawn with CP437 box-drawing characters.

Everything draws into a ``TextGrid`` and reacts to ``InputEvent``s, so the
widgets are testable headless. Menus and dialogs follow Turbo Vision (light
gray, red hotkeys, green selection); panes follow Norton Commander (blue).
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from retro99.input.actions import Action, InputEvent
from retro99.render.palette import Color
from retro99.render.textgrid import TextGrid


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        """Last column inside the rect."""
        return self.x + self.w - 1

    @property
    def bottom(self) -> int:
        """Last row inside the rect."""
        return self.y + self.h - 1

    def inner(self, margin: int = 1) -> Rect:
        return Rect(self.x + margin, self.y + margin, self.w - 2 * margin, self.h - 2 * margin)

    @classmethod
    def centered(cls, w: int, h: int, cols: int, rows: int) -> Rect:
        return cls((cols - w) // 2, (rows - h) // 2, w, h)


@dataclass(frozen=True)
class BoxStyle:
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    # Tees where a single-line divider meets this border.
    tee_top: str
    tee_bottom: str
    tee_left: str
    tee_right: str


SINGLE = BoxStyle("┌", "┐", "└", "┘", "─", "│", "┬", "┴", "├", "┤")
DOUBLE = BoxStyle("╔", "╗", "╚", "╝", "═", "║", "╤", "╧", "╟", "╢")


@dataclass(frozen=True)
class Theme:
    desktop_fg: int = Color.LIGHT_GRAY
    desktop_bg: int = Color.BLACK
    # Norton Commander style panes
    pane_fg: int = Color.LIGHT_CYAN
    pane_bg: int = Color.BLUE
    pane_border: int = Color.LIGHT_CYAN
    pane_title_fg: int = Color.WHITE
    pane_title_focus_fg: int = Color.BLACK
    pane_title_focus_bg: int = Color.CYAN
    pane_label_fg: int = Color.WHITE
    select_fg: int = Color.BLACK
    select_bg: int = Color.CYAN
    select_unfocused_fg: int = Color.YELLOW
    scrollbar_fg: int = Color.CYAN
    # Turbo Vision style menus and dialogs
    menu_fg: int = Color.BLACK
    menu_bg: int = Color.LIGHT_GRAY
    menu_hotkey: int = Color.RED
    menu_select_fg: int = Color.BLACK
    menu_select_bg: int = Color.GREEN
    menu_disabled_fg: int = Color.DARK_GRAY
    dialog_fg: int = Color.BLACK
    dialog_bg: int = Color.LIGHT_GRAY
    dialog_border: int = Color.WHITE
    error_fg: int = Color.WHITE
    error_bg: int = Color.RED
    error_border: int = Color.WHITE
    button_fg: int = Color.BLACK
    button_bg: int = Color.GREEN
    button_focus_fg: int = Color.WHITE
    input_fg: int = Color.WHITE
    input_bg: int = Color.BLUE
    # Norton Commander style function-key bar
    fkey_num_fg: int = Color.WHITE
    fkey_num_bg: int = Color.BLACK
    fkey_label_fg: int = Color.BLACK
    fkey_label_bg: int = Color.CYAN
    shadow_fg: int = Color.DARK_GRAY
    shadow_bg: int = Color.BLACK


DEFAULT_THEME = Theme()


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #


def draw_box(
    grid: TextGrid,
    rect: Rect,
    style: BoxStyle,
    fg: int,
    bg: int,
    *,
    fill: bool = True,
    title: str | None = None,
    title_fg: int | None = None,
    title_bg: int | None = None,
    title_align: str = "center",
) -> None:
    x, y, r, b = rect.x, rect.y, rect.right, rect.bottom
    if fill:
        grid.fill(x + 1, y + 1, rect.w - 2, rect.h - 2, " ", fg, bg)
    grid.put(x, y, style.tl, fg, bg)
    grid.put(r, y, style.tr, fg, bg)
    grid.put(x, b, style.bl, fg, bg)
    grid.put(r, b, style.br, fg, bg)
    for cx in range(x + 1, r):
        grid.put(cx, y, style.h, fg, bg)
        grid.put(cx, b, style.h, fg, bg)
    for cy in range(y + 1, b):
        grid.put(x, cy, style.v, fg, bg)
        grid.put(r, cy, style.v, fg, bg)
    if title:
        draw_title(grid, rect, title, title_fg or fg, title_bg or bg, title_align)


def draw_title(
    grid: TextGrid, rect: Rect, title: str, fg: int, bg: int, align: str = "center"
) -> None:
    label = f" {title} "[: max(rect.w - 4, 0)]
    if align == "left":
        tx = rect.x + 2
    else:
        tx = rect.x + (rect.w - len(label)) // 2
    grid.write(tx, rect.y, label, fg, bg)


def draw_shadow(grid: TextGrid, rect: Rect, theme: Theme = DEFAULT_THEME) -> None:
    """Turbo Vision shadow: one row down, two columns right, keeping characters."""
    grid.recolor(rect.x + rect.w, rect.y + 1, 2, rect.h, theme.shadow_fg, theme.shadow_bg)
    grid.recolor(rect.x + 2, rect.y + rect.h, rect.w, 1, theme.shadow_fg, theme.shadow_bg)


def draw_vdivider(grid: TextGrid, x: int, top: int, bottom: int, outer: BoxStyle, fg: int, bg: int):
    """Single vertical line from border row ``top`` to border row ``bottom``."""
    grid.put(x, top, outer.tee_top, fg, bg)
    for y in range(top + 1, bottom):
        grid.put(x, y, "│", fg, bg)
    grid.put(x, bottom, outer.tee_bottom, fg, bg)


def draw_hdivider(grid: TextGrid, y: int, left: int, right: int, outer: BoxStyle, fg: int, bg: int):
    """Single horizontal line from border column ``left`` to ``right``."""
    grid.put(left, y, outer.tee_left, fg, bg)
    for x in range(left + 1, right):
        grid.put(x, y, "─", fg, bg)
    grid.put(right, y, outer.tee_right, fg, bg)


def draw_scrollbar(
    grid: TextGrid, x: int, y: int, h: int, pos: int, total: int, visible: int, fg: int, bg: int
) -> None:
    """Vertical scrollbar: ▲, a ░ track with a ■ thumb, ▼."""
    if h < 3:
        return
    grid.put(x, y, "▲", fg, bg)
    grid.put(x, y + h - 1, "▼", fg, bg)
    track = h - 2
    grid.fill(x, y + 1, 1, track, "░", fg, bg)
    max_pos = max(total - visible, 1)
    thumb = round(min(pos, max_pos) / max_pos * (track - 1))
    grid.put(x, y + 1 + thumb, "■", fg, bg)


def fit(text: str, width: int, align: str = "left") -> str:
    """Pad or truncate ``text`` to exactly ``width`` cells (``~`` marks a cut, DOS-style)."""
    if width <= 0:
        return ""
    if len(text) > width:
        return text[: width - 1] + "~" if width > 1 else text[:width]
    if align == "right":
        return text.rjust(width)
    if align == "center":
        return text.center(width)
    return text.ljust(width)


def wrap(text: str, width: int) -> list[str]:
    """Word-wrap, keeping blank lines as paragraph breaks."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width) or [""])
    return lines


def parse_hotkey(label: str) -> tuple[str, int]:
    """``"E&xit"`` -> (``"Exit"``, 1). Index is -1 when there is no ``&``."""
    i = label.find("&")
    if i < 0 or i == len(label) - 1:
        return label.replace("&", ""), -1
    return label[:i] + label[i + 1 :], i


def hotkey_char(label: str) -> str:
    text, i = parse_hotkey(label)
    return text[i].lower() if i >= 0 else ""


def draw_hotkey_label(
    grid: TextGrid, x: int, y: int, label: str, fg: int, hot_fg: int, bg: int
) -> int:
    text, i = parse_hotkey(label)
    grid.write(x, y, text, fg, bg)
    if i >= 0:
        grid.put(x + i, y, text[i], hot_fg, bg)
    return len(text)


# --------------------------------------------------------------------------- #
# List box
# --------------------------------------------------------------------------- #


class ListBox:
    """A scrolling, selectable list with letter-jump."""

    def __init__(
        self,
        items: Sequence[str] = (),
        *,
        on_change: Callable[[int], None] | None = None,
        on_activate: Callable[[int], None] | None = None,
        empty_text: str = "(empty)",
    ) -> None:
        self.items: list[str] = list(items)
        self.selected = 0
        self.top = 0
        self.page = 10  # updated from the real height on every draw
        self.on_change = on_change
        self.on_activate = on_activate
        self.empty_text = empty_text

    def set_items(self, items: Sequence[str], selected: int = 0) -> None:
        self.items = list(items)
        self.top = 0
        self.selected = 0
        self.select(selected, notify=False)

    def select(self, index: int, *, notify: bool = True) -> None:
        if not self.items:
            self.selected = 0
            return
        index = max(0, min(index, len(self.items) - 1))
        changed = index != self.selected
        self.selected = index
        self._scroll_into_view()
        if changed and notify and self.on_change:
            self.on_change(index)

    def _scroll_into_view(self) -> None:
        if self.selected < self.top:
            self.top = self.selected
        elif self.selected >= self.top + self.page:
            self.top = self.selected - self.page + 1
        self.top = max(0, min(self.top, max(len(self.items) - self.page, 0)))

    def jump_to_letter(self, ch: str) -> bool:
        """Select the next item starting with ``ch`` after the current one, wrapping."""
        ch = ch.lower()
        n = len(self.items)
        for step in range(1, n + 1):
            i = (self.selected + step) % n
            if self.items[i].lstrip().lower().startswith(ch):
                self.select(i)
                return True
        return False

    def handle(self, ev: InputEvent) -> bool:
        a = ev.action
        if a is Action.UP:
            self.select(self.selected - 1)
        elif a is Action.DOWN:
            self.select(self.selected + 1)
        elif a is Action.PAGE_UP:
            self.select(self.selected - self.page)
        elif a is Action.PAGE_DOWN:
            self.select(self.selected + self.page)
        elif a is Action.HOME:
            self.select(0)
        elif a is Action.END:
            self.select(len(self.items) - 1)
        elif a is Action.SELECT:
            if self.items and self.on_activate:
                self.on_activate(self.selected)
            return bool(self.items)
        elif a is Action.CHAR and not ev.alt and ev.char.isalnum():
            return self.jump_to_letter(ev.char)
        else:
            return False
        return True

    def draw(
        self, grid: TextGrid, rect: Rect, theme: Theme, *, focused: bool, marker: str = "►"
    ) -> None:
        self.page = max(rect.h, 1)
        self._scroll_into_view()
        overflow = len(self.items) > rect.h
        text_w = rect.w - (1 if overflow else 0)
        grid.fill(rect.x, rect.y, rect.w, rect.h, " ", theme.pane_fg, theme.pane_bg)
        if not self.items:
            grid.write(
                rect.x + 1, rect.y, fit(self.empty_text, text_w - 1), theme.pane_fg, theme.pane_bg
            )
            return
        for row in range(rect.h):
            i = self.top + row
            if i >= len(self.items):
                break
            is_sel = i == self.selected
            prefix = marker if is_sel else " "
            line = fit(prefix + self.items[i], text_w)
            if is_sel and focused:
                fg, bg = theme.select_fg, theme.select_bg
            elif is_sel:
                fg, bg = theme.select_unfocused_fg, theme.pane_bg
            else:
                fg, bg = theme.pane_fg, theme.pane_bg
            grid.write(rect.x, rect.y + row, line, fg, bg)
        if overflow:
            draw_scrollbar(
                grid,
                rect.right,
                rect.y,
                rect.h,
                self.top,
                len(self.items),
                rect.h,
                theme.scrollbar_fg,
                theme.pane_bg,
            )


# --------------------------------------------------------------------------- #
# Text input
# --------------------------------------------------------------------------- #


class TextInput:
    """Single-line editable field with a blinking block cursor."""

    def __init__(self, text: str = "", max_len: int = 64) -> None:
        self.text = text[:max_len]
        self.max_len = max_len
        self.pos = len(self.text)
        self._offset = 0

    def handle(self, ev: InputEvent) -> bool:
        a = ev.action
        if a is Action.CHAR and not ev.alt:
            if len(self.text) < self.max_len:
                self.text = self.text[: self.pos] + ev.char + self.text[self.pos :]
                self.pos += len(ev.char)
        elif a is Action.BACKSPACE:
            if self.pos > 0:
                self.text = self.text[: self.pos - 1] + self.text[self.pos :]
                self.pos -= 1
        elif a is Action.DELETE:
            self.text = self.text[: self.pos] + self.text[self.pos + 1 :]
        elif a is Action.LEFT:
            self.pos = max(0, self.pos - 1)
        elif a is Action.RIGHT:
            self.pos = min(len(self.text), self.pos + 1)
        elif a is Action.HOME:
            self.pos = 0
        elif a is Action.END:
            self.pos = len(self.text)
        else:
            return False
        return True

    def draw(
        self, grid: TextGrid, x: int, y: int, w: int, theme: Theme, *, focused: bool = True
    ) -> None:
        if self.pos < self._offset:
            self._offset = self.pos
        elif self.pos >= self._offset + w:
            self._offset = self.pos - w + 1
        visible = self.text[self._offset : self._offset + w]
        grid.write(x, y, visible.ljust(w), theme.input_fg, theme.input_bg)
        if focused:
            grid.cursor = (x + self.pos - self._offset, y)


# --------------------------------------------------------------------------- #
# Menu bar
# --------------------------------------------------------------------------- #


@dataclass
class MenuItem:
    label: str  # "&" marks the hotkey letter
    action: Callable[[], None] | None = None
    hint: str = ""  # shortcut shown on the right, e.g. "F2"
    enabled: bool = True
    checked: Callable[[], bool] | None = None
    separator: bool = False


def separator() -> MenuItem:
    return MenuItem("", separator=True, enabled=False)


@dataclass
class Menu:
    title: str
    items: list[MenuItem] = field(default_factory=list)


class MenuBar:
    """Top-row menu bar with drop-down menus (F10 / Esc / Start to open)."""

    def __init__(self, menus: list[Menu], *, caption: str = "RETRO-99") -> None:
        self.menus = menus
        self.caption = caption
        self.is_open = False
        self.menu_index = 0
        self.item_index = 0

    # positions --------------------------------------------------------------
    def title_positions(self) -> list[int]:
        xs, x = [], 2
        for menu in self.menus:
            xs.append(x)
            x += len(parse_hotkey(menu.title)[0]) + 2
        return xs

    def dropdown_rect(self, cols: int) -> Rect:
        menu = self.menus[self.menu_index]
        label_w = max((len(parse_hotkey(i.label)[0]) for i in menu.items), default=0)
        hint_w = max((len(i.hint) for i in menu.items), default=0)
        w = 2 + 2 + label_w + (hint_w + 2 if hint_w else 0) + 2
        x = min(self.title_positions()[self.menu_index] - 1, cols - w - 2)
        return Rect(max(x, 0), 1, w, len(menu.items) + 2)

    # state ------------------------------------------------------------------
    def open(self, index: int = 0) -> None:
        self.is_open = True
        self.menu_index = index % len(self.menus)
        self.item_index = self._first_selectable(0, 1)

    def close(self) -> None:
        self.is_open = False

    def _items(self) -> list[MenuItem]:
        return self.menus[self.menu_index].items

    def _first_selectable(self, start: int, step: int) -> int:
        items = self._items()
        for k in range(len(items)):
            i = (start + k * step) % len(items)
            if not items[i].separator:
                return i
        return 0

    def _activate(self, item: MenuItem) -> None:
        if item.separator or not item.enabled:
            return
        self.close()
        if item.action:
            item.action()

    def handle(self, ev: InputEvent) -> bool:
        a = ev.action
        if not self.is_open:
            if a is Action.MENU:
                self.open(0)
                return True
            if a is Action.CHAR and ev.alt:
                for i, menu in enumerate(self.menus):
                    if hotkey_char(menu.title) == ev.char.lower():
                        self.open(i)
                        return True
            return False

        items = self._items()
        if a in (Action.BACK, Action.MENU):
            self.close()
        elif a is Action.LEFT:
            self.open(self.menu_index - 1)
        elif a in (Action.RIGHT, Action.TAB):
            self.open(self.menu_index + 1)
        elif a is Action.UP:
            self.item_index = self._first_selectable(self.item_index - 1, -1)
        elif a is Action.DOWN:
            self.item_index = self._first_selectable(self.item_index + 1, 1)
        elif a is Action.HOME:
            self.item_index = self._first_selectable(0, 1)
        elif a is Action.END:
            self.item_index = self._first_selectable(len(items) - 1, -1)
        elif a is Action.SELECT:
            self._activate(items[self.item_index])
        elif a is Action.CHAR:
            ch = ev.char.lower()
            if ev.alt:
                for i, menu in enumerate(self.menus):
                    if hotkey_char(menu.title) == ch:
                        self.open(i)
                        break
            else:
                for item in items:
                    if hotkey_char(item.label) == ch and item.enabled:
                        self._activate(item)
                        break
        return True  # an open menu swallows everything

    # drawing ----------------------------------------------------------------
    def draw(self, grid: TextGrid, theme: Theme, right_text: str = "") -> None:
        grid.fill(0, 0, grid.cols, 1, " ", theme.menu_fg, theme.menu_bg)
        for i, (menu, x) in enumerate(zip(self.menus, self.title_positions(), strict=True)):
            text = parse_hotkey(menu.title)[0]
            if self.is_open and i == self.menu_index:
                grid.write(x - 1, 0, f" {text} ", theme.menu_select_fg, theme.menu_select_bg)
                draw_hotkey_label(
                    grid,
                    x,
                    0,
                    menu.title,
                    theme.menu_select_fg,
                    theme.menu_hotkey,
                    theme.menu_select_bg,
                )
            else:
                draw_hotkey_label(
                    grid, x, 0, menu.title, theme.menu_fg, theme.menu_hotkey, theme.menu_bg
                )
        right = f"{self.caption}  {right_text}".strip() if right_text else self.caption
        grid.write(grid.cols - len(right) - 1, 0, right, theme.menu_fg, theme.menu_bg)
        if self.is_open:
            self._draw_dropdown(grid, theme)

    def _draw_dropdown(self, grid: TextGrid, theme: Theme) -> None:
        rect = self.dropdown_rect(grid.cols)
        draw_box(grid, rect, SINGLE, theme.menu_fg, theme.menu_bg)
        inner_w = rect.w - 2
        for row, item in enumerate(self._items()):
            y = rect.y + 1 + row
            if item.separator:
                draw_hdivider(grid, y, rect.x, rect.right, SINGLE, theme.menu_fg, theme.menu_bg)
                continue
            selected = row == self.item_index
            bg = theme.menu_select_bg if selected else theme.menu_bg
            fg = theme.menu_select_fg if selected else theme.menu_fg
            if not item.enabled:
                fg = theme.menu_disabled_fg
            grid.fill(rect.x + 1, y, inner_w, 1, " ", fg, bg)
            if item.checked is not None and item.checked():
                grid.put(rect.x + 1, y, "√", fg, bg)
            hot = theme.menu_hotkey if item.enabled else fg
            draw_hotkey_label(grid, rect.x + 3, y, item.label, fg, hot, bg)
            if item.hint:
                grid.write(rect.right - 1 - len(item.hint), y, item.hint, fg, bg)
        draw_shadow(grid, rect, theme)


# --------------------------------------------------------------------------- #
# Function-key bar
# --------------------------------------------------------------------------- #


class FunctionKeyBar:
    def __init__(self, items: Sequence[tuple[str, str]]) -> None:
        self.items = list(items)  # (key label, action label), e.g. ("F1", "Help")

    def draw(self, grid: TextGrid, theme: Theme, y: int | None = None) -> None:
        y = grid.rows - 1 if y is None else y
        grid.fill(0, y, grid.cols, 1, " ", theme.fkey_num_fg, theme.fkey_num_bg)
        x = 0
        for key, label in self.items:
            if x >= grid.cols:
                break
            x += grid.write(x, y, key, theme.fkey_num_fg, theme.fkey_num_bg)
            x += grid.write(x, y, f"{label} ", theme.fkey_label_fg, theme.fkey_label_bg)
            x += 1


# --------------------------------------------------------------------------- #
# Dialog
# --------------------------------------------------------------------------- #


class Dialog:
    """Modal message box with buttons. ``result`` is the button index, or None on cancel."""

    def __init__(
        self,
        title: str,
        message: str,
        buttons: Sequence[str] = ("&OK",),
        *,
        error: bool = False,
        default: int = 0,
        min_width: int = 30,
        max_width: int = 64,
    ) -> None:
        self.title = title
        self.message = message
        self.buttons = list(buttons)
        self.error = error
        self.selected = default
        self.min_width = min_width
        self.max_width = max_width
        self.done = False
        self.result: int | None = None

    def _button_labels(self) -> list[str]:
        return [f" {parse_hotkey(b)[0]} " for b in self.buttons]

    def _buttons_width(self) -> int:
        return sum(len(b) + 2 for b in self._button_labels()) - 2

    def layout(self, cols: int, rows: int) -> tuple[Rect, list[str]]:
        longest = max((len(line) for line in self.message.split("\n")), default=0)
        w = max(self.min_width, len(self.title) + 8, self._buttons_width() + 6)
        w = min(max(w, longest + 6), self.max_width, cols - 4)
        lines = wrap(self.message, w - 6)
        h = min(len(lines) + 6, rows - 2)
        return Rect.centered(w, h, cols, rows), lines

    def _finish(self, result: int | None) -> None:
        self.done = True
        self.result = result

    def handle(self, ev: InputEvent) -> bool:
        a = ev.action
        n = len(self.buttons)
        if a in (Action.LEFT, Action.UP):
            self.selected = (self.selected - 1) % n
        elif a in (Action.RIGHT, Action.DOWN, Action.TAB):
            self.selected = (self.selected + 1) % n
        elif a is Action.SELECT:
            self._finish(self.selected)
        elif a is Action.BACK:
            self._finish(None)
        elif a is Action.CHAR:
            for i, b in enumerate(self.buttons):
                if hotkey_char(b) == ev.char.lower():
                    self._finish(i)
                    break
        return True  # modal

    def draw(self, grid: TextGrid, theme: Theme) -> None:
        rect, lines = self.layout(grid.cols, grid.rows)
        if self.error:
            fg, bg, border = theme.error_fg, theme.error_bg, theme.error_border
        else:
            fg, bg, border = theme.dialog_fg, theme.dialog_bg, theme.dialog_border
        draw_box(grid, rect, DOUBLE, border, bg, title=self.title, title_fg=border)
        grid.recolor(rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2, fg, bg)
        for i, line in enumerate(lines[: rect.h - 6]):
            grid.write(rect.x + 3, rect.y + 2 + i, line, fg, bg)
        labels = self._button_labels()
        bx = rect.x + (rect.w - self._buttons_width()) // 2
        by = rect.bottom - 2
        for i, (label, raw) in enumerate(zip(labels, self.buttons, strict=True)):
            focused = i == self.selected
            bfg = theme.button_focus_fg if focused else theme.button_fg
            grid.write(bx, by, label, bfg, theme.button_bg)
            draw_hotkey_label(
                grid,
                bx + 1,
                by,
                raw,
                bfg,
                theme.menu_hotkey if not focused else Color.YELLOW,
                theme.button_bg,
            )
            # Turbo Vision button shadow
            grid.put(bx + len(label), by, "▄", Color.BLACK, bg)
            grid.write(bx + 1, by + 1, "▀" * len(label), Color.BLACK, bg)
            bx += len(label) + 2
        draw_shadow(grid, rect, theme)
