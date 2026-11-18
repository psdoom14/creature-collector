"""Battle-start transitions, GBA style.

    Transition (abstract)     draw(surface, frame, progress)
    ├── WildTransition        two white flashes, then black bars sweep in from alternate sides
    └── TrainerTransition     two white flashes, then a closing black circle

``TransitionScene`` plays one over a frozen picture of the overworld, then swaps
itself for the battle scene.
"""
import math
from abc import ABC, abstractmethod

import pygame

from src.ui.scene import Scene


class Transition(ABC):
    duration = 1.2
    FLASH_END = 0.35  # the first part of every transition: two quick white flashes

    def draw(self, surface: pygame.Surface, frame: pygame.Surface, progress: float) -> None:
        surface.blit(frame, (0, 0))
        if progress < self.FLASH_END:
            flash = math.sin(progress / self.FLASH_END * math.pi * 2) ** 2
            veil = pygame.Surface(surface.get_size())
            veil.fill((248, 248, 248))
            veil.set_alpha(int(220 * flash))
            surface.blit(veil, (0, 0))
        else:
            self.cover(surface, (progress - self.FLASH_END) / (1 - self.FLASH_END))

    @abstractmethod
    def cover(self, surface: pygame.Surface, p: float) -> None:
        """Draw how much of the screen is black, ``p`` from 0 (none) to 1 (all)."""


class WildTransition(Transition):
    BARS = 8

    def cover(self, surface, p):
        w, h = surface.get_size()
        bar_h = h / self.BARS
        for i in range(self.BARS):
            length = int(w * min(1.0, p * 1.15))
            x = 0 if i % 2 == 0 else w - length
            pygame.draw.rect(surface, (0, 0, 0), (x, int(i * bar_h), length, int(bar_h) + 1))


class TrainerTransition(Transition):
    def cover(self, surface, p):
        w, h = surface.get_size()
        radius = int((1 - p) * math.hypot(w, h) / 2)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        if radius > 0:
            pygame.draw.circle(mask, (0, 0, 0, 0), (w // 2, h // 2), radius)
        surface.blit(mask, (0, 0))


class TransitionScene(Scene):
    """Plays ``transition`` over a frozen frame, then replaces itself with ``next_scene``."""
    MUSIC = "battle"

    def __init__(self, engine, frame: pygame.Surface, next_scene: Scene, transition: Transition):
        super().__init__(engine)
        self.frame = frame.copy()
        self.next_scene = next_scene
        self.transition = transition
        self.t = 0.0
        self.finished = False

    def handle_event(self, event) -> None:
        pass  # nothing to press during a transition

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= self.transition.duration and not self.finished:
            self.finished = True
            self.engine.replace_scene(self.next_scene)

    def draw(self, surface: pygame.Surface) -> None:
        self.transition.draw(surface, self.frame, min(1.0, self.t / self.transition.duration))
