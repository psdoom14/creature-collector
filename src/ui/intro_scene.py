"""New-game intro: the professor's welcome speech and typing your name."""
import math
from typing import List

import pygame

from src.model.direction import Direction
from src.ui.components import (
    TextBox, draw_crisp_text, draw_fitted_text, draw_gba_panel, get_font, small_font,
)
from src.ui.scene import Scene
from src.ui.sprite_renderer import SpriteRenderer
from src.ui.world_renderer import CharacterSprites

ADVANCE_KEYS = (pygame.K_z, pygame.K_SPACE, pygame.K_RETURN)
PROFESSOR = "PROF. CEDAR"
SHOWCASE_SPECIES = 25

BEFORE_NAME = [
    "Hello there! Welcome to the world of creatures!",
    "My name is CEDAR. People call me the Creature Professor.",
    "This world is full of creatures. They live in tall grass, rivers, caves...",
    "Some people keep them as partners. Others battle with them.",
    "As for me, I study them.",
    "But first, tell me about yourself. What is your name?",
]
AFTER_NAME = [
    "Right! So your name is {name}!",
    "{name}! Your very own adventure is about to begin!",
    "Come and see me at my lab in Fernvale Town. A partner is waiting for you!",
]


class IntroScene(Scene):
    """Modes: TALK (professor speaking), NAME (typing the player's name)."""
    MUSIC = "menu"

    MAX_NAME = 8

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.textbox = TextBox(pygame.Rect(4, 110, 232, 46))
        self.pages: List[str] = list(BEFORE_NAME)
        self.page = 0
        self.mode = "TALK"
        self.name = ""
        self.named = False
        self.timer = 0.0
        self.textbox.set_message(self.pages[0])

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.mode == "NAME":
            self._name_key(event)
        elif event.key in ADVANCE_KEYS:
            self._advance()

    def _advance(self) -> None:
        if not self.textbox.is_finished_typing:
            self.textbox.advance()
            return
        self.page += 1
        if self.page < len(self.pages):
            self.textbox.set_message(self.pages[self.page])
        elif not self.named:
            self.mode = "NAME"
        else:
            self._begin_adventure()

    def _name_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_RETURN:
            if self.name.strip():
                self._confirm_name()
        elif event.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        else:
            ch = getattr(event, "unicode", "") or ""
            if len(ch) == 1 and (ch.isalnum() or ch in " -") and len(self.name) < self.MAX_NAME:
                self.name += ch.upper()

    def _confirm_name(self) -> None:
        self.name = self.name.strip()
        self.engine.game_state.trainer.rename(self.name)
        self.named = True
        self.mode = "TALK"
        self.pages = [line.format(name=self.name) for line in AFTER_NAME]
        self.page = 0
        self.textbox.set_message(self.pages[0])

    def _begin_adventure(self) -> None:
        from src.ui.overworld_scene import OverworldScene  # avoid an import cycle
        self.engine.change_scene(OverworldScene(self.engine))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.timer += dt
        self.textbox.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            shade = 200 + int(40 * y / surface.get_height())
            pygame.draw.line(surface, (shade - 40, shade - 16, shade), (0, y), (240, y))
        pygame.draw.ellipse(surface, (168, 184, 208), pygame.Rect(72, 88, 96, 18))

        prof = CharacterSprites.get("brown", Direction.DOWN)
        big = pygame.transform.scale(prof, (prof.get_width() * 3, prof.get_height() * 3))
        surface.blit(big, (120 - big.get_width() // 2, 98 - big.get_height()))

        if 2 <= self.page <= 4 and not self.named:
            mon = SpriteRenderer.get_creature_sprite(SHOWCASE_SPECIES, "", "Electric", is_back=False,
                                                     size=(48, 48))
            bob = int(math.sin(self.timer * 3) * 2)
            surface.blit(mon, (172, 46 + bob))

        draw_gba_panel(surface, pygame.Rect(4, 4, 110, 18))
        draw_fitted_text(surface, PROFESSOR, 10, 7, 98, self.font_sm)

        if self.mode == "NAME":
            self._draw_name_entry(surface)
        else:
            self.textbox.draw(surface)

    def _draw_name_entry(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(4, 110, 232, 46)
        draw_gba_panel(surface, panel)
        draw_fitted_text(surface, "YOUR NAME?", panel.x + 10, panel.y + 4, 120, self.font_sm)
        shown = self.name + ("_" if int(self.timer * 2) % 2 == 0 and len(self.name) < self.MAX_NAME else "")
        draw_crisp_text(surface, shown, panel.x + 10, panel.y + 16, self.font)
        draw_fitted_text(surface, "TYPE, THEN ENTER", panel.x + 120, panel.y + 4, 104,
                         self.font_sm, align="right")
