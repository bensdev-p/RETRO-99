import pygame

from retro99.render.palette import Color, rgb
from retro99.render.textgrid import GridRenderer, TextGrid


def test_defaults_are_80x25():
    g = TextGrid()
    assert (g.cols, g.rows) == (80, 25)
    assert g.cell(0, 0) == (" ", Color.LIGHT_GRAY, Color.BLACK)


def test_write_clips_at_edge_and_width():
    g = TextGrid(10, 2)
    assert g.write(7, 0, "HELLO") == 3
    assert g.row_text(0) == "       HEL"
    assert g.write(0, 1, "ABCDEF", width=2) == 2
    assert g.row_text(1).startswith("AB ")


def test_put_out_of_bounds_is_ignored():
    g = TextGrid(4, 4)
    g.put(-1, 0, "X")
    g.put(4, 4, "X")
    assert "X" not in g.text()


def test_put_none_keeps_colors_and_recolor_keeps_chars():
    g = TextGrid(4, 1)
    g.put(0, 0, "A", Color.RED, Color.BLUE)
    g.put(0, 0, "B")
    assert g.cell(0, 0) == ("B", Color.RED, Color.BLUE)
    g.recolor(0, 0, 4, 1, fg=Color.WHITE)
    assert g.cell(0, 0) == ("B", Color.WHITE, Color.BLUE)


def test_fill_and_clear():
    g = TextGrid(5, 3)
    g.fill(1, 1, 2, 2, "#", Color.YELLOW, Color.GREEN)
    assert g.text().splitlines() == ["     ", " ##  ", " ##  "]
    g.cursor = (1, 1)
    g.clear()
    assert g.text().strip() == "" and g.cursor is None


def test_renderer_draws_fg_bg_and_cursor(tiny_font):
    g = TextGrid(2, 1)
    g.put(0, 0, "A", Color.YELLOW, Color.BLUE)
    r = GridRenderer(tiny_font, 2, 1)
    surf = r.render(g)
    assert surf.get_size() == (16, 16)
    assert surf.get_at((0, 0))[:3] == rgb(Color.YELLOW)  # glyph's lit top row
    assert surf.get_at((0, 5))[:3] == rgb(Color.BLUE)
    g.cursor = (0, 0)
    surf = r.render(g, cursor_on=True)
    assert surf.get_at((0, 5))[:3] == rgb(Color.YELLOW)  # inverted
    surf = r.render(g, cursor_on=False)
    assert surf.get_at((0, 5))[:3] == rgb(Color.BLUE)


def test_renderer_only_redraws_changed_cells(tiny_font):
    g = TextGrid(2, 1)
    r = GridRenderer(tiny_font, 2, 1)
    r.render(g)
    r.surface.fill((1, 2, 3))  # scribble; unchanged cells must not be redrawn
    r.render(g)
    assert r.surface.get_at((0, 5))[:3] == (1, 2, 3)
    r.invalidate()
    r.render(g)
    assert r.surface.get_at((0, 5))[:3] == rgb(Color.BLACK)
    assert isinstance(r.surface, pygame.Surface)
