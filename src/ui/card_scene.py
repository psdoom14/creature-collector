"""Trainer card: name, money, Pokédex count, play time and earned badges."""
import pygame

from src.ui.components import draw_fitted_text, draw_gba_panel, get_font, small_font
from src.ui.scene import Scene

CLOSE_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
BADGE_SLOTS = 4


class CardScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in CLOSE_KEYS:
            self.engine.pop_scene()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((64, 104, 168))
        state = self.engine.game_state
        card = pygame.Rect(8, 8, 224, 144)
        draw_gba_panel(surface, card, fill_color=(232, 240, 248))
        draw_fitted_text(surface, "TRAINER CARD", card.x + 8, card.y + 4, 200, self.font)

        rows = [
            ("NAME", state.trainer.name),
            ("MONEY", f"${state.trainer.money}"),
            ("POKÉDEX", str(state.pokedex.caught_count)),
            ("TIME", state.play_time_text),
        ]
        for i, (label, value) in enumerate(rows):
            y = card.y + 26 + i * 14
            draw_fitted_text(surface, label, card.x + 10, y, 80, self.font_sm)
            draw_fitted_text(surface, value, card.x + 92, y, 120, self.font_sm, align="right")

        draw_fitted_text(surface, "BADGES", card.x + 10, card.y + 86, 80, self.font_sm)
        names = state.badge_case.names
        for slot in range(BADGE_SLOTS):
            box = pygame.Rect(card.x + 12 + slot * 52, card.y + 100, 46, 34)
            pygame.draw.rect(surface, (200, 208, 224), box, border_radius=4)
            pygame.draw.rect(surface, (96, 104, 128), box, 1, border_radius=4)
            if slot < len(names):
                pygame.draw.polygon(surface, (248, 200, 64), [
                    (box.centerx, box.y + 4), (box.right - 12, box.centery - 2),
                    (box.centerx, box.bottom - 12), (box.x + 12, box.centery - 2)])
                pygame.draw.polygon(surface, (160, 112, 32), [
                    (box.centerx, box.y + 4), (box.right - 12, box.centery - 2),
                    (box.centerx, box.bottom - 12), (box.x + 12, box.centery - 2)], 1)
                label = names[slot].replace(" BADGE", "")
                draw_fitted_text(surface, label, box.x + 1, box.bottom - 11, box.width - 2,
                                 self.font_sm, align="center")
