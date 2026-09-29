"""Keyboard to ``InputEvent`` translation."""

from __future__ import annotations

import pygame

from retro99.input.actions import Action, InputEvent

_KEYMAP: dict[int, Action] = {
    pygame.K_UP: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_LEFT: Action.LEFT,
    pygame.K_RIGHT: Action.RIGHT,
    pygame.K_PAGEUP: Action.PAGE_UP,
    pygame.K_PAGEDOWN: Action.PAGE_DOWN,
    pygame.K_HOME: Action.HOME,
    pygame.K_END: Action.END,
    pygame.K_RETURN: Action.SELECT,
    pygame.K_KP_ENTER: Action.SELECT,
    pygame.K_ESCAPE: Action.BACK,
    pygame.K_TAB: Action.TAB,
    pygame.K_BACKSPACE: Action.BACKSPACE,
    pygame.K_DELETE: Action.DELETE,
    pygame.K_F10: Action.MENU,
}

_FKEYS: dict[int, int] = {getattr(pygame, f"K_F{n}"): n for n in range(1, 13) if n != 10}


def translate_key(key: int, mod: int = 0, text: str = "") -> InputEvent | None:
    """Map a KEYDOWN (key code, modifiers, produced text) to an InputEvent."""
    alt = bool(mod & pygame.KMOD_ALT)
    shift = bool(mod & pygame.KMOD_SHIFT)
    if key in _KEYMAP:
        return InputEvent(_KEYMAP[key], alt=alt, shift=shift)
    if key in _FKEYS:
        return InputEvent(Action.FUNCTION, number=_FKEYS[key], alt=alt, shift=shift)
    if alt and pygame.K_a <= key <= pygame.K_z:
        # With Alt held, SDL often produces no text; use the key name instead.
        return InputEvent(Action.CHAR, char=chr(key), alt=True, shift=shift)
    if text and text.isprintable() and not (mod & pygame.KMOD_CTRL):
        return InputEvent(Action.CHAR, char=text, shift=shift)
    return None


def translate(event: pygame.event.Event) -> InputEvent | None:
    if event.type != pygame.KEYDOWN:
        return None
    return translate_key(event.key, event.mod, getattr(event, "unicode", ""))
