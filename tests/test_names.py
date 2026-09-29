import pytest

from retro99.library.names import normalize_title, parse_name, slugify, sort_key


@pytest.mark.parametrize(
    ("stem", "title", "region"),
    [
        ("Super Fake Quest (USA) [!]", "Super Fake Quest", "USA"),
        ("Legend of Fakeland, The (Japan)", "The Legend of Fakeland", "Japan"),
        ("Game (USA, Europe) (Rev 1) [b]", "Game", "USA, Europe"),
        ("Plain Title", "Plain Title", ""),
        ("Under_Scored (World)", "Under Scored", "World"),
        ("Adventure, An - The Sequel (USA)", "An Adventure - The Sequel", "USA"),
        ("(Proto)", "(Proto)", ""),
    ],
)
def test_parse_name(stem, title, region):
    parsed = parse_name(stem)
    assert (parsed.title, parsed.region) == (title, region)


def test_disc_numbers():
    assert parse_name("Fake Saga (USA) (Disc 2)").disc == 2
    assert parse_name("Fake Saga (Disk 1 of 3)").disc == 1
    assert parse_name("Fake Saga").disc is None
    assert normalize_title("Fake Saga (USA) (Disc 2)") == "Fake Saga"


def test_sort_key_and_slug():
    assert sort_key("The Lion King") == "lion king"
    assert sort_key("Another World") == "another world"
    assert slugify("Super Fake Quest (USA) [!]") == "super-fake-quest-usa"
    assert slugify("!!!") == "game"
