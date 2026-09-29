"""Device-independent input events.

Screens and widgets only ever see ``InputEvent``s, never raw pygame events, so
keyboard, gamepad (Phase 4) and tests all drive the UI the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Action(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    HOME = auto()
    END = auto()
    SELECT = auto()  # Enter / gamepad A
    BACK = auto()  # Esc / gamepad B
    MENU = auto()  # F10 / gamepad Start
    TAB = auto()
    BACKSPACE = auto()
    DELETE = auto()
    FUNCTION = auto()  # F1-F12; see InputEvent.number
    CHAR = auto()  # printable character; see InputEvent.char


@dataclass(frozen=True)
class InputEvent:
    action: Action
    char: str = ""
    number: int = 0
    alt: bool = False
    shift: bool = False

    @classmethod
    def key(cls, char: str, *, alt: bool = False) -> InputEvent:
        return cls(Action.CHAR, char=char, alt=alt)

    @classmethod
    def fkey(cls, number: int) -> InputEvent:
        return cls(Action.FUNCTION, number=number)
