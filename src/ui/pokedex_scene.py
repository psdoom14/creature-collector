"""Pokédex viewer scene displaying seen and captured species."""
import pygame
from src.ui.scene import Scene
from src.ui.components import draw_gba_panel, get_font, COLOR_TEXT_DARK, TYPE_COLORS
from src.ui.sprite_renderer import SpriteRenderer


class PokedexScene(Scene):
    """GBA Pokédex screen with scrollable species list."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = get_font(9)
        self.species_list = self.engine.data_loader.get_all_species()
        self.selected_index = 0
        self.scroll_offset = 0
        self.visible_rows = 5

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        total = len(self.species_list)
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected_index = (self.selected_index - 1) % total
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
            elif self.selected_index == total - 1:
                self.scroll_offset = max(0, total - self.visible_rows)

        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected_index = (self.selected_index + 1) % total
            if self.selected_index >= self.scroll_offset + self.visible_rows:
                self.scroll_offset = self.selected_index - self.visible_rows + 1
            elif self.selected_index == 0:
                self.scroll_offset = 0

        elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_RETURN, pygame.K_SPACE):
            self.engine.pop_scene()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((192, 56, 48))  # Pokédex classic red casing
        dex = self.engine.game_state.pokedex
        caught_cnt, total, pct = dex.get_completion(len(self.species_list))

        # Header info
        draw_gba_panel(surface, pygame.Rect(4, 4, 232, 22))
        title = self.font.render(f"POKÉDEX  CAUGHT:{caught_cnt}  SEEN:{len(dex.seen)}", True, COLOR_TEXT_DARK)
        surface.blit(title, (10, 8))

        # Main scrollable list
        draw_gba_panel(surface, pygame.Rect(4, 28, 140, 110))
        y = 32
        for i in range(self.scroll_offset, min(len(self.species_list), self.scroll_offset + self.visible_rows)):
            sp = self.species_list[i]
            sp_id = sp["id"]
            is_sel = (i == self.selected_index)
            is_caught = dex.is_caught(sp_id)
            is_seen = dex.is_seen(sp_id)

            if is_sel:
                highlight = pygame.Rect(8, y - 2, 132, 19)
                pygame.draw.rect(surface, (232, 208, 144), highlight, border_radius=2)
                arr = self.font_sm.render("▶", True, (180, 40, 30))
                surface.blit(arr, (10, y + 2))

            # Ball icon if caught
            ball_str = "●" if is_caught else " "
            ball_lbl = self.font_sm.render(ball_str, True, (200, 40, 40) if is_caught else (160, 160, 160))
            surface.blit(ball_lbl, (20, y + 2))

            # Number & Name
            display_name = sp["name"].upper() if is_seen else "----------"
            txt = self.font_sm.render(f"#{sp_id:03d} {display_name}", True, COLOR_TEXT_DARK)
            surface.blit(txt, (32, y + 2))

            y += 20

        # Detail Panel on right
        draw_gba_panel(surface, pygame.Rect(148, 28, 88, 110))
        cur_sp = self.species_list[self.selected_index]
        cur_seen = dex.is_seen(cur_sp["id"])

        if cur_seen:
            # Sprite
            sprite = SpriteRenderer.get_creature_sprite(
                cur_sp["id"], cur_sp["name"], cur_sp["types"][0], is_back=False, size=(44, 44)
            )
            surface.blit(sprite, (170, 34))

            # Types
            t_y = 82
            for t in cur_sp.get("types", []):
                t_color = TYPE_COLORS.get(t, (120, 120, 120))
                t_rect = pygame.Rect(154, t_y, 76, 12)
                pygame.draw.rect(surface, t_color, t_rect, border_radius=2)
                t_txt = self.font_sm.render(t.upper(), True, (255, 255, 255))
                surface.blit(t_txt, (158, t_y + 1))
                t_y += 14
        else:
            unknown = self.font.render("???", True, (120, 120, 120))
            surface.blit(unknown, (184, 60))

        # Bottom hint
        draw_gba_panel(surface, pygame.Rect(4, 140, 232, 16))
        hint = self.font_sm.render("▲▼ Scroll | ESC/X to return", True, COLOR_TEXT_DARK)
        surface.blit(hint, (12, 142))
