"""Bag screen (from the overworld pause menu): browse items and use them on party creatures."""
import pygame

from src.ui.components import (
    MenuBox, TextBox, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text,
)
from src.ui.scene import Scene

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)

LIST_RECT = pygame.Rect(4, 22, 140, 98)
DESC_RECT = pygame.Rect(148, 22, 88, 98)


class BagScene(Scene):
    """Modes: LIST (pick an item), CHOOSE_TARGET (pick a creature), MESSAGE (show the result)."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.textbox = TextBox(pygame.Rect(4, 122, 232, 34))
        self.mode = "LIST"
        self.menu = self._build_item_menu()
        self.party_menu: MenuBox = None
        self.chosen_item_id: str = ""

    # ------------------------------------------------------------------
    @property
    def _bag(self):
        return self.engine.game_state.trainer.bag

    @property
    def _party(self):
        return self.engine.game_state.trainer.party

    def _build_item_menu(self) -> MenuBox:
        options = [f"{it.name} x{it.quantity}" for it in self._bag.items] or ["(EMPTY)"]
        menu = MenuBox(LIST_RECT, options, columns=1, visible_rows=6)
        old = getattr(self, "menu", None)
        if old:
            menu.selected_index = min(old.selected_index, len(options) - 1)
            menu._keep_selection_visible()
        return menu

    def _selected_item(self):
        items = self._bag.items
        if 0 <= self.menu.selected_index < len(items):
            return items[self.menu.selected_index]
        return None

    def _show_message(self, text: str) -> None:
        self.textbox.set_message(text)
        self.mode = "MESSAGE"

    def _open_party_menu(self) -> None:
        options = []
        for c in self._party:
            hp = "FAINTED" if c.is_fainted else f"{c.current_hp}/{c.max_hp}"
            options.append(f"{c.name.upper()[:10]}  L{c.level}  {hp}")
        self.party_menu = MenuBox(pygame.Rect(36, 22, 200, 98), options, columns=1, visible_rows=6)
        self.mode = "CHOOSE_TARGET"

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key

        if self.mode == "LIST":
            if key in CANCEL_KEYS:
                self.engine.pop_scene()
                return
            if self.menu.handle_input(key) is None:
                return
            item = self._selected_item()
            if item is None:
                return
            if not item.usable_in_field:  # polymorphic: CatchBall answers False
                self._show_message(f"The {item.name} can only be used in battle.")
                return
            self.chosen_item_id = item.id
            self._open_party_menu()

        elif self.mode == "CHOOSE_TARGET":
            if key in CANCEL_KEYS:
                self.mode = "LIST"
                return
            choice = self.party_menu.handle_input(key)
            if choice is None:
                return
            target = self._party.creatures[choice]
            message = self._bag.use(self.chosen_item_id, target)
            self.menu = self._build_item_menu()
            self._show_message(message)

        elif self.mode == "MESSAGE":
            if key in CONFIRM_KEYS + CANCEL_KEYS and not self.textbox.advance():
                self.mode = "LIST"

    def update(self, dt: float) -> None:
        self.textbox.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((216, 160, 72))
        draw_gba_panel(surface, pygame.Rect(4, 2, 232, 18))
        draw_fitted_text(surface, "BAG", 12, 3, 120, self.font)
        draw_fitted_text(surface, f"${self.engine.game_state.trainer.money}", 132, 6, 96,
                         self.font_sm, align="right")

        self.menu.draw(surface)

        draw_gba_panel(surface, DESC_RECT)
        item = self._selected_item()
        if item:
            lines = wrap_text(item.description, DESC_RECT.width - 12, self.font_sm)
            for i, line in enumerate(lines[:7]):
                draw_fitted_text(surface, line, DESC_RECT.x + 6, DESC_RECT.y + 5 + i * 13,
                                 DESC_RECT.width - 12, self.font_sm)

        if self.mode == "CHOOSE_TARGET":
            self.party_menu.draw(surface)
            item = self._bag.get(self.chosen_item_id)
            name = item.name if item else "it"
            draw_gba_panel(surface, self.textbox.rect)
            draw_fitted_text(surface, f"Use {name} on which creature?", 14, 130, 212, self.font_sm)
        elif self.mode == "MESSAGE":
            self.textbox.draw(surface)
        else:
            draw_gba_panel(surface, self.textbox.rect)
            draw_fitted_text(surface, "Z: USE      X: CLOSE", 14, 130, 212, self.font_sm)
