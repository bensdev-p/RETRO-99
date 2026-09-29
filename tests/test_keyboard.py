import pygame

from retro99.input.actions import Action, InputEvent
from retro99.input.keyboard import translate_key


def test_navigation_keys():
    assert translate_key(pygame.K_UP) == InputEvent(Action.UP)
    assert translate_key(pygame.K_RETURN).action is Action.SELECT
    assert translate_key(pygame.K_ESCAPE).action is Action.BACK
    assert translate_key(pygame.K_F10).action is Action.MENU


def test_function_keys():
    assert translate_key(pygame.K_F2) == InputEvent.fkey(2)
    assert translate_key(pygame.K_F12).number == 12


def test_text_and_alt_letters():
    assert translate_key(pygame.K_a, 0, "a") == InputEvent.key("a")
    assert translate_key(pygame.K_x, pygame.KMOD_LALT, "") == InputEvent.key("x", alt=True)
    assert translate_key(pygame.K_c, pygame.KMOD_LCTRL, "\x03") is None
    assert translate_key(pygame.K_LSHIFT, pygame.KMOD_LSHIFT, "") is None
