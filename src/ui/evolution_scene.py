"""Evolution sequence: "What? X is evolving!" -> flashing silhouettes -> new form.

Press X/Esc during the flashing to stop the evolution (it will be offered again
after the next battle, as in the classic games).
"""
from typing import List, Optional

import pygame

from src.model.creature import Creature
from src.ui.components import TextBox
from src.ui.scene import Scene
from src.ui.sprite_renderer import SpriteRenderer

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)

ANIMATION_SECONDS = 3.0
SPRITE_SIZE = (64, 64)
SPRITE_POS = (88, 24)


def _silhouette(sprite: pygame.Surface) -> pygame.Surface:
    """A white copy of ``sprite`` that keeps its transparency."""
    white = sprite.copy()
    white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
    return white


class EvolutionScene(Scene):
    """Plays the evolution sequence for each creature in ``creatures``, one after another."""

    def __init__(self, engine, creatures: List[Creature]):
        super().__init__(engine)
        self.queue: List[Creature] = list(creatures)
        self.textbox = TextBox(pygame.Rect(4, 110, 232, 46))
        self.creature: Optional[Creature] = None
        self.new_species: Optional[dict] = None
        self.old_sprite: Optional[pygame.Surface] = None
        self.new_sprite: Optional[pygame.Surface] = None
        self.stage = "INTRO"  # INTRO, ANIMATING, DONE
        self.timer = 0.0
        self.show_new = False
        self._start_next()

    def _start_next(self) -> None:
        if not self.queue:
            self.engine.pop_scene()
            return
        self.creature = self.queue.pop(0)
        self.new_species = self.engine.data_loader.get_species_data(self.creature.evolves_into)
        if not self.new_species:
            self._start_next()
            return
        c, s = self.creature, self.new_species
        self.old_sprite = SpriteRenderer.get_creature_sprite(
            c.species_id, c.name, c.primary_type, is_back=False, size=SPRITE_SIZE)
        self.new_sprite = SpriteRenderer.get_creature_sprite(
            s["id"], s["name"], s.get("types", ["Normal"])[0], is_back=False, size=SPRITE_SIZE)
        self.stage = "INTRO"
        self.timer = 0.0
        self.show_new = False
        self.textbox.set_message(f"What? {c.name} is evolving!")

    def _finish(self, cancelled: bool) -> None:
        c = self.creature
        if cancelled:
            self.textbox.set_message(f"Huh? {c.name} stopped evolving!")
        else:
            old_name = c.name
            c.evolve(self.new_species)
            self.engine.game_state.pokedex.register_caught(c.species_id)
            self.show_new = True
            self.textbox.set_message(f"Congratulations! Your {old_name} evolved into {c.name}!")
        self.stage = "DONE"

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.creature is None:
            return
        if self.stage == "INTRO" and event.key in CONFIRM_KEYS:
            if not self.textbox.is_finished_typing:
                self.textbox.advance()
            else:
                self.stage = "ANIMATING"
                self.timer = 0.0
        elif self.stage == "ANIMATING" and event.key in CANCEL_KEYS:
            self._finish(cancelled=True)
        elif self.stage == "DONE" and event.key in CONFIRM_KEYS:
            if not self.textbox.is_finished_typing:
                self.textbox.advance()
            else:
                self._start_next()

    def update(self, dt: float) -> None:
        self.textbox.update(dt)
        if self.stage != "ANIMATING":
            return
        self.timer += dt
        if self.timer >= ANIMATION_SECONDS:
            self._finish(cancelled=False)
            return
        # Flip between old and new forms, faster and faster.
        progress = self.timer / ANIMATION_SECONDS
        flips_per_second = 2 + 14 * progress
        self.show_new = int(self.timer * flips_per_second) % 2 == 1

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((24, 32, 56))
        if self.creature is None:
            return
        sprite = self.new_sprite if self.show_new else self.old_sprite
        if self.stage == "ANIMATING":
            sprite = _silhouette(sprite)
            # Soft glow that pulses with each flip.
            glow = (72, 88, 136) if self.show_new else (48, 60, 100)
            pygame.draw.ellipse(surface, glow, pygame.Rect(SPRITE_POS[0] - 12, SPRITE_POS[1] - 8, 88, 80))
        surface.blit(sprite, SPRITE_POS)
        self.textbox.draw(surface)
