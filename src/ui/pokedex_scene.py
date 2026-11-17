"""Pokédex viewer scene displaying seen and captured species."""
import pygame
from src.ui.scene import Scene
from src.ui.components import TYPE_COLORS, draw_fitted_text, draw_gba_panel, get_font, small_font
from src.ui.sprite_renderer import SpriteRenderer


ROW_H = 18
VISIBLE_ROWS = 6


def _draw_mini_ball(surface: pygame.Surface, cx: int, cy: int) -> None:
    """7px catch-ball icon: red top, white bottom, dark outline."""
    pygame.draw.circle(surface, (248, 248, 248), (cx, cy), 3)
    pygame.draw.rect(surface, (224, 48, 40), pygame.Rect(cx - 3, cy - 3, 7, 3))
    pygame.draw.circle(surface, (40, 40, 48), (cx, cy), 4, 1)
    pygame.draw.line(surface, (40, 40, 48), (cx - 3, cy), (cx + 3, cy))


class PokedexScene(Scene):
    """GBA Pokédex screen with scrollable species list."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.species_list = self.engine.data_loader.get_all_species()
        self.selected_index = 0
        self.scroll_offset = 0
        self.visible_rows = VISIBLE_ROWS

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
        surface.fill((192, 56, 48))  # Pokédex red casing
        dex = self.engine.game_state.pokedex

        # Header: title on the left, counters right-aligned
        draw_gba_panel(surface, pygame.Rect(4, 4, 232, 18))
        draw_fitted_text(surface, "POKÉDEX", 10, 5, 90, self.font)
        draw_fitted_text(surface, f"SEEN {dex.seen_count}   OWN {dex.caught_count}",
                         104, 8, 126, self.font_sm, align="right")

        # Scrollable species list
        draw_gba_panel(surface, pygame.Rect(4, 24, 140, 112))
        for row, i in enumerate(range(self.scroll_offset,
                                      min(len(self.species_list), self.scroll_offset + self.visible_rows))):
            sp = self.species_list[i]
            y = 28 + row * ROW_H
            if i == self.selected_index:
                pygame.draw.rect(surface, (232, 208, 144), pygame.Rect(7, y - 1, 134, ROW_H - 1), border_radius=2)
                pts = [(9, y + 3), (14, y + 7), (9, y + 11)]
                pygame.draw.polygon(surface, (216, 48, 32), pts)
            if dex.is_caught(sp["id"]):
                _draw_mini_ball(surface, 21, y + 7)
            name = sp["name"].upper() if dex.is_seen(sp["id"]) else "----------"
            draw_fitted_text(surface, f"#{sp['id']:03d} {name}", 28, y + 2, 112, self.font_sm)

        # Detail panel
        draw_gba_panel(surface, pygame.Rect(148, 24, 88, 112))
        cur = self.species_list[self.selected_index]
        if dex.is_seen(cur["id"]):
            sprite = SpriteRenderer.get_creature_sprite(
                cur["id"], cur["name"], cur["types"][0], is_back=False, size=(44, 44))
            surface.blit(sprite, (170, 28))
            t_y = 76
            for t in cur.get("types", []):
                t_rect = pygame.Rect(154, t_y, 76, 12)
                pygame.draw.rect(surface, TYPE_COLORS.get(t, (120, 120, 120)), t_rect, border_radius=2)
                draw_fitted_text(surface, t.upper(), 156, t_y, 72, self.font_sm,
                                 color=(255, 255, 255), shadow_color=(60, 60, 60), align="center")
                t_y += 14
            status = "CAUGHT" if dex.is_caught(cur["id"]) else "SEEN"
            draw_fitted_text(surface, status, 152, 118, 80, self.font_sm, align="center")
        else:
            draw_fitted_text(surface, "???", 152, 60, 80, self.font, color=(120, 120, 120), align="center")

        # Footer
        draw_gba_panel(surface, pygame.Rect(4, 140, 232, 16))
        draw_fitted_text(surface, "UP/DOWN: SCROLL      X: BACK", 12, 142, 216, self.font_sm)
