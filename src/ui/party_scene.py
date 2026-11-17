"""Party screen: every party creature with level, HP bar and HP numbers in fixed columns."""
import pygame

from src.ui.components import (
    COLOR_TEXT_DARK, HPBar, draw_fitted_text, draw_gba_panel, draw_status_pill, get_font, small_font,
)
from src.ui.scene import Scene
from src.ui.sprite_renderer import SpriteRenderer

# Column layout inside each 228px-wide slot (native 240x160 coordinates).
#  arrow | icon | NAME         | LEVEL | HP BAR       | HP NUMBERS
SLOT_X, SLOT_W, SLOT_H, SLOT_GAP, FIRST_SLOT_Y = 6, 228, 18, 1, 22
COL_ICON_X = 16
COL_NAME_X, COL_NAME_W = 34, 62
COL_LEVEL_X, COL_LEVEL_W = 100, 30
COL_HP_BAR_X, COL_HP_BAR_W = 136, 46
COL_HP_NUM_X, COL_HP_NUM_W = 186, 44

FAINTED_RED = (200, 48, 40)


class PartyScene(Scene):
    """GBA Party screen displaying all party members."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.selected_index = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        size = max(1, self.engine.game_state.trainer.party.size)
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected_index = (self.selected_index - 1) % size
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected_index = (self.selected_index + 1) % size
        elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_RETURN, pygame.K_SPACE):
            self.engine.pop_scene()

    def update(self, dt: float) -> None:
        pass

    def _draw_slot(self, surface: pygame.Surface, creature, y: int, selected: bool) -> None:
        rect = pygame.Rect(SLOT_X, y, SLOT_W, SLOT_H)
        draw_gba_panel(surface, rect)
        if selected:
            pygame.draw.rect(surface, (240, 120, 60), rect, 2, border_radius=4)
            pts = [(rect.x + 3, y + 5), (rect.x + 8, y + 9), (rect.x + 3, y + 13)]
            pygame.draw.polygon(surface, (216, 48, 32), pts)

        icon = SpriteRenderer.get_creature_sprite(
            creature.species_id, creature.name, creature.primary_type, False, (16, 16))
        surface.blit(icon, (COL_ICON_X, y + 1))

        text_y = y + 3
        draw_fitted_text(surface, creature.name.upper(), COL_NAME_X, text_y, COL_NAME_W, self.font_sm)
        draw_fitted_text(surface, f"Lv{creature.level}", COL_LEVEL_X, text_y, COL_LEVEL_W, self.font_sm)

        if creature.is_fainted:
            draw_fitted_text(surface, "FAINTED", COL_HP_BAR_X, text_y, COL_HP_BAR_W, self.font_sm,
                             color=FAINTED_RED)
        elif creature.status_effect:
            draw_status_pill(surface, COL_HP_BAR_X, y + 4, creature.status_effect)
            bar = HPBar(COL_HP_BAR_X + 24, y + 7, COL_HP_BAR_W - 24, 4)
            bar.set_hp(creature.current_hp, creature.max_hp, immediate=True)
            bar.draw(surface)
        else:
            bar = HPBar(COL_HP_BAR_X, y + 7, COL_HP_BAR_W, 4)
            bar.set_hp(creature.current_hp, creature.max_hp, immediate=True)
            bar.draw(surface)

        draw_fitted_text(surface, f"{creature.current_hp}/{creature.max_hp}", COL_HP_NUM_X, text_y,
                         COL_HP_NUM_W, self.font_sm, align="right")

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((80, 120, 160))
        draw_gba_panel(surface, pygame.Rect(4, 2, 232, 18))
        draw_fitted_text(surface, "PARTY", 12, 3, 216, self.font)

        party = self.engine.game_state.trainer.party
        for i, creature in enumerate(party.creatures):
            y = FIRST_SLOT_Y + i * (SLOT_H + SLOT_GAP)
            self._draw_slot(surface, creature, y, i == self.selected_index)

        draw_gba_panel(surface, pygame.Rect(4, 138, 232, 18))
        draw_fitted_text(surface, "X: BACK", 12, 141, 216, self.font_sm)
