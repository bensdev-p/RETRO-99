"""The physical display: integer scaling with letterboxing, fullscreen or windowed.

On the Pi this runs fullscreen through SDL's KMS/DRM backend. ``close()`` and
``open()`` exist so the launcher can hand DRM/KMS to a child process and take
it back afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from retro99.render.crt import CrtEffect


@dataclass(frozen=True)
class Viewport:
    x: int
    y: int
    w: int
    h: int
    scale: int  # integer scale factor; 0 when the window is smaller than 1x


def compute_viewport(window: tuple[int, int], logical: tuple[int, int]) -> Viewport:
    """Largest integer scale of ``logical`` that fits ``window``, centered.

    If even 1x does not fit, shrink to fit while keeping the aspect ratio.
    """
    ww, wh = window
    lw, lh = logical
    scale = min(ww // lw, wh // lh)
    if scale >= 1:
        w, h = lw * scale, lh * scale
    else:
        ratio = min(ww / lw, wh / lh)
        w, h = max(1, int(lw * ratio)), max(1, int(lh * ratio))
    return Viewport((ww - w) // 2, (wh - h) // 2, w, h, scale)


class Display:
    def __init__(
        self,
        logical_size: tuple[int, int],
        *,
        fullscreen: bool,
        window_scale: int = 2,
        crt: CrtEffect | None = None,
        caption: str = "RETRO-99",
    ) -> None:
        self.logical_size = logical_size
        self.fullscreen = fullscreen
        self.window_scale = max(1, window_scale)
        self.crt = crt or CrtEffect()
        self.caption = caption
        self._screen: pygame.Surface | None = None
        self._scaled: pygame.Surface | None = None
        self._viewport: Viewport | None = None

    @property
    def is_open(self) -> bool:
        return self._screen is not None

    def open(self) -> None:
        pygame.display.init()
        pygame.display.set_caption(self.caption)
        if self.fullscreen:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        else:
            lw, lh = self.logical_size
            size = (lw * self.window_scale, lh * self.window_scale)
            self._screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self._relayout()

    def close(self) -> None:
        """Release the display entirely so a child process can take DRM/KMS."""
        self._screen = None
        self._scaled = None
        self._viewport = None
        pygame.display.quit()

    def resized(self) -> None:
        """Call after a VIDEORESIZE / WINDOWSIZECHANGED event."""
        if self._screen is not None:
            self._screen = pygame.display.get_surface()
            self._relayout()

    def _relayout(self) -> None:
        assert self._screen is not None
        self._viewport = compute_viewport(self._screen.get_size(), self.logical_size)
        self._scaled = pygame.Surface((self._viewport.w, self._viewport.h))
        self._screen.fill((0, 0, 0))

    def present(self, frame: pygame.Surface) -> None:
        if self._screen is None or self._viewport is None or self._scaled is None:
            return
        vp = self._viewport
        pygame.transform.scale(frame, (vp.w, vp.h), self._scaled)
        self.crt.apply(self._scaled, vp.scale)
        self._screen.blit(self._scaled, (vp.x, vp.y))
        pygame.display.flip()
