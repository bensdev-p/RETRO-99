from retro99.input.actions import Action, InputEvent
from retro99.render.palette import Color
from retro99.render.textgrid import TextGrid
from retro99.render.widgets import (
    DEFAULT_THEME,
    DOUBLE,
    SINGLE,
    Dialog,
    FunctionKeyBar,
    ListBox,
    Menu,
    MenuBar,
    MenuItem,
    Rect,
    TextInput,
    draw_box,
    draw_scrollbar,
    draw_shadow,
    draw_vdivider,
    fit,
    hotkey_char,
    parse_hotkey,
    separator,
    wrap,
)

T = DEFAULT_THEME


def ev(action: Action) -> InputEvent:
    return InputEvent(action)


# primitives ----------------------------------------------------------------


def test_draw_box_corners_edges_and_title():
    g = TextGrid(12, 4)
    draw_box(g, Rect(0, 0, 12, 4), DOUBLE, Color.WHITE, Color.BLUE, title="Hi")
    assert g.text().splitlines() == [
        "╔═══ Hi ═══╗",
        "║          ║",
        "║          ║",
        "╚══════════╝",
    ]
    assert g.cell(5, 1)[2] == Color.BLUE


def test_left_aligned_title_and_divider_tees():
    g = TextGrid(10, 3)
    draw_box(g, Rect(0, 0, 10, 3), DOUBLE, 1, 1, title="A", title_align="left")
    draw_vdivider(g, 5, 0, 2, DOUBLE, 1, 1)
    assert g.text().splitlines() == ["╔═ A ╤═══╗", "║    │   ║", "╚════╧═══╝"]


def test_shadow_is_offset_down_one_right_two_and_keeps_chars():
    g = TextGrid(10, 5)
    g.fill(0, 0, 10, 5, "x", Color.WHITE, Color.BLUE)
    draw_shadow(g, Rect(1, 1, 3, 2), T)
    shaded = {(x, y) for x, y, _, fg, _ in g.cells() if fg == T.shadow_fg}
    assert shaded == {(4, 2), (5, 2), (4, 3), (5, 3), (3, 3)}
    assert g.cell(4, 2) == ("x", T.shadow_fg, T.shadow_bg)


def test_scrollbar_thumb_positions():
    g = TextGrid(1, 6)
    draw_scrollbar(g, 0, 0, 6, 0, 100, 6, 1, 1)
    assert [g.cell(0, y)[0] for y in range(6)] == ["▲", "■", "░", "░", "░", "▼"]
    draw_scrollbar(g, 0, 0, 6, 94, 100, 6, 1, 1)
    assert g.cell(0, 4)[0] == "■"


def test_fit_wrap_and_hotkeys():
    assert fit("abc", 5) == "abc  "
    assert fit("abcdef", 4) == "abc~"
    assert fit("ab", 4, "right") == "  ab"
    assert wrap("one two three", 7) == ["one two", "three"]
    assert wrap("a\n\nb", 10) == ["a", "", "b"]
    assert parse_hotkey("E&xit") == ("Exit", 1)
    assert parse_hotkey("None") == ("None", -1)
    assert hotkey_char("&File") == "f"


# list box ------------------------------------------------------------------


def test_listbox_navigation_and_clamping():
    changes = []
    lb = ListBox([f"item {i}" for i in range(30)], on_change=changes.append)
    lb.page = 10
    lb.handle(ev(Action.UP))
    assert lb.selected == 0 and changes == []
    lb.handle(ev(Action.PAGE_DOWN))
    assert lb.selected == 10 and lb.top == 1
    lb.handle(ev(Action.END))
    assert lb.selected == 29 and lb.top == 20
    lb.handle(ev(Action.HOME))
    assert (lb.selected, lb.top) == (0, 0)
    assert changes == [10, 29, 0]


def test_listbox_letter_jump_cycles_and_wraps():
    lb = ListBox(["Alpha", "Bravo", "Beta", "Charlie"])
    lb.handle(InputEvent.key("b"))
    assert lb.selected == 1
    lb.handle(InputEvent.key("B"))
    assert lb.selected == 2
    lb.handle(InputEvent.key("b"))
    assert lb.selected == 1
    assert lb.handle(InputEvent.key("z")) is False
    assert lb.handle(InputEvent.key("a", alt=True)) is False


def test_listbox_activate_and_empty():
    hits = []
    lb = ListBox(["x"], on_activate=hits.append)
    assert lb.handle(ev(Action.SELECT))
    assert hits == [0]
    empty = ListBox([], on_activate=hits.append)
    assert empty.handle(ev(Action.SELECT)) is False
    assert empty.handle(ev(Action.DOWN)) is True and empty.selected == 0


def test_listbox_draw_highlight_marker_and_scrollbar():
    g = TextGrid(12, 3)
    lb = ListBox(["one", "two", "three", "four"])
    lb.select(1)
    lb.draw(g, Rect(0, 0, 12, 3), T, focused=True)
    assert g.row_text(0).startswith(" one")
    assert g.row_text(1).startswith("►two")
    assert g.cell(1, 1)[1:] == (T.select_fg, T.select_bg)
    assert g.cell(11, 0)[0] == "▲"
    lb.draw(g, Rect(0, 0, 12, 3), T, focused=False)
    assert g.cell(1, 1)[1:] == (T.select_unfocused_fg, T.pane_bg)


def test_listbox_draw_empty_text():
    g = TextGrid(12, 2)
    ListBox([], empty_text="No games").draw(g, Rect(0, 0, 12, 2), T, focused=True)
    assert "No games" in g.row_text(0)


# text input ----------------------------------------------------------------


def test_text_input_editing_and_cursor():
    ti = TextInput(max_len=5)
    for c in "abc":
        ti.handle(InputEvent.key(c))
    ti.handle(ev(Action.LEFT))
    ti.handle(ev(Action.BACKSPACE))
    assert (ti.text, ti.pos) == ("ac", 1)
    ti.handle(ev(Action.HOME))
    ti.handle(ev(Action.DELETE))
    assert ti.text == "c"
    for c in "123456":
        ti.handle(InputEvent.key(c))
    assert ti.text == "1234c"  # max_len reached; extra keys ignored
    g = TextGrid(10, 1)
    ti.handle(ev(Action.END))
    ti.draw(g, 2, 0, 3, T)
    assert g.cursor == (4, 0)  # scrolled so the cursor stays inside the field


# menu bar ------------------------------------------------------------------


def make_menu(log):
    return MenuBar(
        [
            Menu(
                "&File",
                [
                    MenuItem("&Open", lambda: log.append("open"), "F3"),
                    separator(),
                    MenuItem("&Disabled", lambda: log.append("bad"), enabled=False),
                    MenuItem("&Quit", lambda: log.append("quit")),
                ],
            ),
            Menu("&Help", [MenuItem("&About", lambda: log.append("about"))]),
        ]
    )


def test_menu_opens_navigates_and_skips_separators():
    log = []
    mb = make_menu(log)
    assert mb.handle(ev(Action.DOWN)) is False  # closed menus ignore input
    assert mb.handle(ev(Action.MENU)) and mb.is_open
    mb.handle(ev(Action.DOWN))
    assert mb.item_index == 2  # skipped the separator
    mb.handle(ev(Action.SELECT))
    assert mb.is_open and log == []  # disabled items do nothing
    mb.handle(ev(Action.DOWN))
    mb.handle(ev(Action.SELECT))
    assert log == ["quit"] and not mb.is_open


def test_menu_wraps_left_right_and_hotkeys():
    log = []
    mb = make_menu(log)
    mb.open(0)
    mb.handle(ev(Action.LEFT))
    assert mb.menu_index == 1
    mb.handle(InputEvent.key("a"))
    assert log == ["about"]
    assert mb.handle(InputEvent.key("f", alt=True)) and mb.menu_index == 0
    mb.handle(InputEvent.key("o"))
    assert log == ["about", "open"]
    mb.open(0)
    mb.handle(ev(Action.BACK))
    assert not mb.is_open


def test_menu_draw_bar_and_dropdown():
    g = TextGrid(40, 10)
    mb = make_menu([])
    mb.draw(g, T, "12:18")
    assert g.row_text(0).startswith("  File  Help")
    assert g.row_text(0).rstrip().endswith("RETRO-99  12:18")
    assert g.cell(2, 0)[1] == T.menu_hotkey
    mb.open(0)
    mb.draw(g, T)
    assert "Open" in g.row_text(2) and "F3" in g.row_text(2)
    assert g.row_text(3)[1] == "├"


# function-key bar and dialog -----------------------------------------------


def test_function_key_bar():
    g = TextGrid(40, 2)
    FunctionKeyBar([("F1", "Help"), ("F10", "Menu")]).draw(g, T)
    assert g.row_text(1).startswith("F1Help  F10Menu")
    assert g.cell(0, 1)[1:] == (T.fkey_num_fg, T.fkey_num_bg)
    assert g.cell(2, 1)[1:] == (T.fkey_label_fg, T.fkey_label_bg)


def test_dialog_buttons_and_cancel():
    d = Dialog("Q", "Sure?", ("&Yes", "&No"), default=1)
    d.handle(ev(Action.RIGHT))
    assert d.selected == 0
    d.handle(ev(Action.SELECT))
    assert d.done and d.result == 0
    d = Dialog("Q", "Sure?", ("&Yes", "&No"))
    d.handle(InputEvent.key("n"))
    assert d.result == 1
    d = Dialog("Q", "Sure?")
    d.handle(ev(Action.BACK))
    assert d.done and d.result is None


def test_dialog_layout_wraps_and_centers():
    d = Dialog("Title", "word " * 40, max_width=40)
    rect, lines = d.layout(80, 25)
    assert rect.w == 40 and rect.x == 20
    assert all(len(line) <= 34 for line in lines)
    g = TextGrid()
    d.draw(g, T)
    assert "Title" in g.row_text(rect.y)
    assert g.cell(rect.x, rect.y)[0] == "╔"
    error = Dialog("Err", "bad", error=True)
    g2 = TextGrid()
    error.draw(g2, T)
    r2, _ = error.layout(80, 25)
    assert g2.cell(r2.x + 1, r2.y + 1)[2] == T.error_bg


def test_single_style_is_consistent():
    assert SINGLE.tl == "┌" and DOUBLE.tee_top == "╤"
