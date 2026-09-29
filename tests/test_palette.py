from retro99.render.palette import PALETTE, Color, display_name, rgb


def test_sixteen_colors_with_valid_rgb():
    assert len(PALETTE) == 16 == len(Color)
    for triple in PALETTE:
        assert len(triple) == 3
        assert all(0 <= v <= 255 for v in triple)


def test_cga_brown_and_named_lookup():
    assert rgb(Color.BROWN) == (0xAA, 0x55, 0x00)
    assert rgb(Color.WHITE) == (0xFF, 0xFF, 0xFF)
    assert display_name(Color.LIGHT_CYAN) == "Light Cyan"
