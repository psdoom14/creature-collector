"""Shop screen, opened by talking to a Shopkeeper: buy items, or sell what's in your bag.

Every rule (prices, money, stock) lives in ``src.model.shop.Shop``; this screen only
picks an item and a quantity and shows the result.
"""
from typing import List, Optional

import pygame

from src.model.shop import Shop
from src.ui.components import (
    MenuBox, TextBox, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text,
)
from src.ui.scene import Scene

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)

LIST_RECT = pygame.Rect(4, 22, 140, 98)
DESC_RECT = pygame.Rect(148, 22, 88, 98)
TEXT_RECT = pygame.Rect(4, 122, 232, 34)
CHOICE_RECT = pygame.Rect(164, 64, 72, 56)
QTY_RECT = pygame.Rect(148, 90, 88, 30)
VISIBLE_ROWS = 6


class ShopScene(Scene):
    """Modes: CHOICE (buy/sell/quit), LIST (pick an item), QUANTITY, MESSAGE."""

    def __init__(self, engine, shop: Shop, title: str = "SUPPLY SHOP"):
        super().__init__(engine)
        self.shop = shop
        self.title = title
        self.font = get_font(10)
        self.font_sm = small_font()
        self.textbox = TextBox(TEXT_RECT)
        self.choice_menu = MenuBox(CHOICE_RECT, ["BUY", "SELL", "QUIT"], columns=1)
        self.list_menu: Optional[MenuBox] = None
        self.selling = False
        self.quantity = 1
        self.mode = "CHOICE"
        self._after_message = "CHOICE"

    # ------------------------------------------------------------------
    @property
    def _trainer(self):
        return self.engine.game_state.trainer

    def _entries(self) -> List:
        """Items on the current list: the shop's catalog, or the bag when selling."""
        return list(self._trainer.bag.items) if self.selling else list(self.shop.catalog)

    def _open_list(self, selling: bool) -> None:
        self.selling = selling
        names = [item.name for item in self._entries()] or ["(NOTHING TO SELL)"]
        old = self.list_menu if self.list_menu and self.mode != "CHOICE" else None
        self.list_menu = MenuBox(LIST_RECT, names, columns=1, visible_rows=VISIBLE_ROWS)
        if old:
            self.list_menu.selected_index = min(old.selected_index, len(names) - 1)
            self.list_menu.scroll_row = min(old.scroll_row, max(0, len(names) - VISIBLE_ROWS))
            self.list_menu._keep_selection_visible()
        self.mode = "LIST"

    def _selected(self):
        entries = self._entries()
        if self.list_menu and 0 <= self.list_menu.selected_index < len(entries):
            return entries[self.list_menu.selected_index]
        return None

    def _unit_price(self, item) -> int:
        return self.shop.sell_price_of(item.id) if self.selling else item.price

    def _max_quantity(self, item) -> int:
        if self.selling:
            return item.quantity
        return self.shop.max_affordable(self._trainer, item.id)

    def _show_message(self, text: str, then: str) -> None:
        self.textbox.set_message(text)
        self._after_message = then
        self.mode = "MESSAGE"

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        handler = getattr(self, f"_key_{self.mode.lower()}")
        handler(event.key)

    def _key_choice(self, key: int) -> None:
        if key in CANCEL_KEYS:
            self.engine.pop_scene()
            return
        choice = self.choice_menu.handle_input(key)
        if choice == 0:
            self._open_list(selling=False)
        elif choice == 1:
            self._open_list(selling=True)
        elif choice == 2:
            self.engine.pop_scene()

    def _key_list(self, key: int) -> None:
        if key in CANCEL_KEYS:
            self.mode = "CHOICE"
            return
        if self.list_menu.handle_input(key) is None:
            return
        item = self._selected()
        if item is None:
            return
        if self._unit_price(item) <= 0:
            self._show_message(f"I'm sorry, I can't buy the {item.name}.", "LIST")
        elif self._max_quantity(item) <= 0:
            self._show_message("You don't have enough money.", "LIST")
        else:
            self.quantity = 1
            self.mode = "QUANTITY"

    def _key_quantity(self, key: int) -> None:
        item = self._selected()
        if key in CANCEL_KEYS or item is None:
            self.mode = "LIST"
            return
        top = self._max_quantity(item)
        step = {pygame.K_UP: 1, pygame.K_w: 1, pygame.K_DOWN: -1, pygame.K_s: -1,
                pygame.K_RIGHT: 10, pygame.K_d: 10, pygame.K_LEFT: -10, pygame.K_a: -10}.get(key)
        if step is not None:
            q = self.quantity + step
            # Up past the top wraps to 1 and down past 1 wraps to the top, like the games.
            self.quantity = 1 if q > top and step == 1 else top if q < 1 and step == -1 else max(1, min(top, q))
            return
        if key in CONFIRM_KEYS:
            action = self.shop.sell if self.selling else self.shop.buy
            result = action(self._trainer, item.id, self.quantity)
            self._show_message(result.message, "LIST")

    def _key_message(self, key: int) -> None:
        if key in CONFIRM_KEYS + CANCEL_KEYS and not self.textbox.advance():
            if self._after_message == "LIST":
                self._open_list(self.selling)   # rebuild: the bag may have changed
            else:
                self.mode = self._after_message

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.textbox.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((120, 168, 216))
        draw_gba_panel(surface, pygame.Rect(4, 2, 232, 18))
        draw_fitted_text(surface, self.title, 12, 3, 120, self.font)
        draw_fitted_text(surface, f"${self._trainer.money}", 132, 6, 96, self.font_sm, align="right")

        if self.mode == "CHOICE":
            self._draw_welcome(surface)
            return

        self._draw_list(surface)
        self._draw_description(surface)
        if self.mode == "QUANTITY":
            self._draw_quantity(surface)
        if self.mode == "MESSAGE":
            self.textbox.draw(surface)
        else:
            draw_gba_panel(surface, TEXT_RECT)
            hint = "UP/DOWN: 1  L/R: 10  Z: OK" if self.mode == "QUANTITY" else (
                "Z: SELL      X: BACK" if self.selling else "Z: BUY      X: BACK")
            draw_fitted_text(surface, hint, 14, 130, 212, self.font_sm)

    def _draw_welcome(self, surface: pygame.Surface) -> None:
        draw_gba_panel(surface, pygame.Rect(4, 22, 156, 98))
        lines = wrap_text("Welcome! We have catch balls, medicine and more. "
                          "We also buy items at half price.", 140, self.font_sm)
        for i, line in enumerate(lines[:6]):
            draw_fitted_text(surface, line, 12, 30 + i * 14, 140, self.font_sm)
        self.choice_menu.draw(surface)
        draw_gba_panel(surface, TEXT_RECT)
        draw_fitted_text(surface, "What would you like to do?", 14, 130, 212, self.font_sm)

    def _draw_list(self, surface: pygame.Surface) -> None:
        self.list_menu.draw(surface)
        menu = self.list_menu
        row_h = (menu.rect.height - 10) // VISIBLE_ROWS
        for i, item in enumerate(self._entries()):
            r = i - menu.scroll_row
            if not 0 <= r < VISIBLE_ROWS:
                continue
            y = menu.rect.y + 6 + r * row_h
            label = f"x{item.quantity}" if self.selling else f"${item.price}"
            draw_fitted_text(surface, label, menu.rect.right - 50, y, 42, self.font_sm, align="right")

    def _draw_description(self, surface: pygame.Surface) -> None:
        draw_gba_panel(surface, DESC_RECT)
        item = self._selected()
        if item is None:
            return
        width = DESC_RECT.width - 12
        held = self._trainer.get_item(item.id)
        footer = f"IN BAG: {held.quantity if held else 0}"
        if self.selling:
            each = self.shop.sell_price_of(item.id)
            footer = f"PAYS ${each}" if each else "CAN'T SELL"
        # Let hyphenated words ("high-performance") break across lines.
        lines = wrap_text(item.description.replace("-", "- "), width, self.font_sm)
        for i, line in enumerate(lines[:5]):
            draw_fitted_text(surface, line, DESC_RECT.x + 6, DESC_RECT.y + 5 + i * 13, width, self.font_sm)
        draw_fitted_text(surface, footer, DESC_RECT.x + 6, DESC_RECT.bottom - 16, width, self.font_sm)

    def _draw_quantity(self, surface: pygame.Surface) -> None:
        item = self._selected()
        draw_gba_panel(surface, QTY_RECT)
        total = self._unit_price(item) * self.quantity
        draw_fitted_text(surface, f"x{self.quantity:02d}", QTY_RECT.x + 8, QTY_RECT.y + 9, 34, self.font)
        draw_fitted_text(surface, f"${total}", QTY_RECT.x + 40, QTY_RECT.y + 10, 40, self.font_sm,
                         align="right")
