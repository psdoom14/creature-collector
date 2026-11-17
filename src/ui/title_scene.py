"""Title screen: "PRESS START", then CONTINUE / NEW GAME / QUIT."""
import math

import pygame

from src.ui.components import (
    MenuBox, draw_crisp_text, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text,
)
from src.ui.scene import Scene
from src.ui.sprite_renderer import SpriteRenderer

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)

TITLE_LINES = ("CREATURE", "COLLECTOR")
SHOWCASE_SPECIES = 6


class TitleScene(Scene):
    """First screen of the game. Stages: PRESS_START -> MENU."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font_big = get_font(16)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.timer = 0.0
        self.stage = "PRESS_START"
        self.saved = engine.peek_save()
        # Shown when a save file exists but can't be loaded
        self.warning = "Your save file is damaged and can't be loaded." if engine.save_problem else ""
        self.options = (["CONTINUE"] if self.saved else []) + ["NEW GAME", "QUIT"]
        self.menu = MenuBox(pygame.Rect(8, 70, 96, 14 * len(self.options) + 10), self.options)

    def _start(self, option: str) -> None:
        from src.ui.overworld_scene import OverworldScene  # imported here to avoid a cycle

        if option == "CONTINUE":
            if not self.engine.continue_game():
                return
        elif option == "NEW GAME":
            from src.ui.intro_scene import IntroScene
            self.engine.new_game()
            self.engine.change_scene(IntroScene(self.engine))
            return
        elif option == "QUIT":
            self.engine.is_running = False
            return
        self.engine.change_scene(OverworldScene(self.engine))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.stage == "PRESS_START":
            if event.key in CONFIRM_KEYS:
                self.stage = "MENU"
            return
        if event.key in CANCEL_KEYS:
            self.stage = "PRESS_START"
            return
        choice = self.menu.handle_input(event.key)
        if choice is not None:
            self._start(self.options[choice])

    def update(self, dt: float) -> None:
        self.timer += dt

    def _draw_background(self, surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            shade = int(40 + 60 * y / surface.get_height())
            pygame.draw.line(surface, (24, shade // 2 + 16, shade + 40), (0, y), (surface.get_width(), y))

    def _draw_save_summary(self, surface: pygame.Surface) -> None:
        if not self.saved or self.options[self.menu.selected_index] != "CONTINUE":
            return
        panel = pygame.Rect(110, 70, 126, 62)
        draw_gba_panel(surface, panel)
        t = self.saved.trainer
        rows = [
            ("PLAYER", t.name),
            ("BADGES", str(self.saved.badges)),
            ("POKÉDEX", str(self.saved.pokedex.caught_count)),
            ("TIME", self.saved.play_time_text),
        ]
        for i, (label, value) in enumerate(rows):
            y = panel.y + 6 + i * 13
            draw_fitted_text(surface, label, panel.x + 8, y, 56, self.font_sm)
            draw_fitted_text(surface, value, panel.x + 64, y, 54, self.font_sm, align="right")

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)

        # Title text with a slight bob
        bob = int(math.sin(self.timer * 2) * 2)
        for i, line in enumerate(TITLE_LINES):
            w = self.font_big.size(line)[0]
            draw_crisp_text(surface, line, (240 - w) // 2, 10 + i * 20 + bob, self.font_big,
                            color=(248, 216, 64), shadow_color=(96, 48, 16))

        if self.stage == "PRESS_START":
            sprite = SpriteRenderer.get_creature_sprite(SHOWCASE_SPECIES, "", "Fire", is_back=False, size=(64, 64))
            surface.blit(sprite, (88, 56))
            if int(self.timer * 2) % 2 == 0:
                draw_fitted_text(surface, "PRESS ENTER", 0, 132, 240, self.font,
                                 color=(248, 248, 248), shadow_color=(32, 32, 48), align="center")
        else:
            self.menu.draw(surface)
            self._draw_save_summary(surface)
            if self.warning:
                box = pygame.Rect(110, 70, 126, 46)
                draw_gba_panel(surface, box)
                for i, line in enumerate(wrap_text(self.warning, box.width - 12, self.font_sm)[:3]):
                    draw_fitted_text(surface, line, box.x + 6, box.y + 5 + i * 12, box.width - 12,
                                     self.font_sm, color=(184, 40, 32))
            draw_fitted_text(surface, "Z: SELECT   X: BACK", 0, 146, 240, self.font_sm,
                             color=(248, 248, 248), shadow_color=(32, 32, 48), align="center")
