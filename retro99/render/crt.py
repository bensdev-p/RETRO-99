"""Optional CRT post-process, applied to the scaled frame. Off by default.

Currently scanlines only; curvature is planned for the Pi performance pass
(Phase 6), where it can be measured against the frame budget.
"""

from __future__ import annotations

import pygame


class CrtEffect:
    def __init__(self, enabled: bool = False, strength: int = 96) -> None:
        self.enabled = enabled
        self.strength = max(0, min(strength, 255))
        self._overlay: pygame.Surface | None = None
        self._overlay_key: tuple[int, int, int] | None = None

    def _build_overlay(self, size: tuple[int, int], scale: int) -> pygame.Surface:
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        shade = (0, 0, 0, self.strength)
        # Darken the last scaled row of every source row, like a CRT's gaps.
        for y in range(scale - 1, size[1], scale):
            overlay.fill(shade, pygame.Rect(0, y, size[0], 1))
        return overlay

    def apply(self, surface: pygame.Surface, scale: int) -> None:
        """Draw scanlines onto ``surface`` in place. Needs a scale of 2 or more."""
        if not self.enabled or scale < 2:
            return
        key = (*surface.get_size(), scale)
        if self._overlay is None or self._overlay_key != key:
            self._overlay = self._build_overlay(surface.get_size(), scale)
            self._overlay_key = key
        surface.blit(self._overlay, (0, 0))
