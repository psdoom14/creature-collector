"""Party scene showing party members, levels, HP, and types."""
import pygame
from src.ui.scene import Scene
from src.ui.components import draw_gba_panel, HPBar, get_font, COLOR_TEXT_DARK, TYPE_COLORS
from src.ui.sprite_renderer import SpriteRenderer


class PartyScene(Scene):
    """GBA Party screen displaying all active party members."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = get_font(9)
        self.selected_index = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        party = self.engine.game_state.trainer.party
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected_index = (self.selected_index - 1) % max(1, party.size)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected_index = (self.selected_index + 1) % max(1, party.size)
        elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_RETURN, pygame.K_SPACE):
            self.engine.pop_scene()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((80, 120, 160))  # Dark blue GBA party background
        draw_gba_panel(surface, pygame.Rect(4, 4, 232, 20))
        title = self.font.render("POKÉMON PARTY", True, COLOR_TEXT_DARK)
        surface.blit(title, (12, 8))

        party = self.engine.game_state.trainer.party
        y = 28
        for i, c in enumerate(party.creatures):
            is_sel = (i == self.selected_index)
            rect = pygame.Rect(6, y, 228, 19)
            draw_gba_panel(surface, rect)

            if is_sel:
                pygame.draw.rect(surface, (240, 120, 60), rect, 2, border_radius=4)
                arr = self.font.render("▶", True, (240, 80, 40))
                surface.blit(arr, (10, y + 4))

            # Small icon
            icon = SpriteRenderer.get_creature_sprite(c.species_id, c.name, c.primary_type, False, (16, 16))
            surface.blit(icon, (24, y + 2))

            # Name and Level
            name_txt = self.font.render(f"{c.name.upper():<11}", True, COLOR_TEXT_DARK)
            lvl_txt = self.font_sm.render(f"Lv.{c.level}", True, COLOR_TEXT_DARK)
            surface.blit(name_txt, (44, y + 4))
            surface.blit(lvl_txt, (105, y + 5))

            # HP Bar and numbers
            hp_bar = HPBar(145, y + 7, 45, 5)
            hp_bar.set_hp(c.current_hp, c.max_hp, immediate=True)
            hp_bar.draw(surface)

            hp_num = self.font_sm.render(f"{c.current_hp}/{c.max_hp}", True, COLOR_TEXT_DARK)
            surface.blit(hp_num, (194, y + 5))

            y += 21

        # Instructions
        draw_gba_panel(surface, pygame.Rect(4, 138, 232, 18))
        hint = self.font_sm.render("Press ESC/X to return", True, COLOR_TEXT_DARK)
        surface.blit(hint, (12, 142))
