"""Debug menu (F1 or ` in the overworld): level up, add/remove creatures, items and money.

Meant for demos and testing. Every change goes through ``src/model/debug_tools.py``
and the normal model methods, so the game's rules still hold.
"""
from typing import List, Optional

import pygame

from src.model import debug_tools
from src.model.errors import RuleViolation
from src.ui.components import MenuBox, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text
from src.ui.scene import Scene

CONFIRM = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
BACK = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)
MAIN_OPTIONS = ["LEVEL UP", "ADD CREATURE", "REMOVE CREATURE", "ITEMS", "MONEY", "HEAL PARTY", "CLOSE"]
LEVEL_STEPS = ["+1", "+5", "+10", "BACK"]
MONEY_STEPS = ["+1000", "+10000", "-1000", "SET TO 0", "BACK"]
LIST_RECT = pygame.Rect(4, 22, 232, 98)


class DebugScene(Scene):
    """Pages: MAIN, LEVEL_PICK, LEVEL_AMOUNT, ADD, REMOVE, ITEMS, MONEY."""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.page = "MAIN"
        self.menu = MenuBox(pygame.Rect(4, 22, 120, 98), MAIN_OPTIONS, visible_rows=7)
        self.list_menu: Optional[MenuBox] = None
        self.sub_menu: Optional[MenuBox] = None
        self.message = "Z: choose   X: back / close. Changes apply at once."
        self.add_level = 5
        self.level_target = 0
        self.item_catalog = engine.data_loader.get_all_items()

    # ------------------------------------------------------------------
    @property
    def _state(self):
        return self.engine.game_state

    @property
    def _trainer(self):
        return self._state.trainer

    def _party_options(self) -> List[str]:
        return [f"{c.name.upper()}  Lv{c.level}  {c.current_hp}/{c.max_hp}" for c in self._trainer.party]

    def _species_options(self) -> List[str]:
        return [f"#{sp['id']:03d} {sp['name'].upper()}" for sp in self.engine.data_loader.get_all_species()]

    def _item_options(self) -> List[str]:
        bag = self._trainer.bag
        options = []
        for data in self.item_catalog:
            item = bag.get(data["id"])
            options.append(f"{data['name']}  x{item.quantity if item else 0}")
        return options

    def _open_list(self, page: str, options: List[str], keep_index: bool = False) -> None:
        old = self.list_menu.selected_index if (keep_index and self.list_menu) else 0
        self.list_menu = MenuBox(LIST_RECT, options or ["(NONE)"], visible_rows=7)
        self.list_menu.selected_index = min(old, len(self.list_menu.options) - 1)
        self.list_menu._keep_selection_visible()
        self.page = page

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        handler = getattr(self, f"_key_{self.page.lower()}")
        handler(event.key)

    def _key_main(self, key: int) -> None:
        if key in BACK:
            self._close()
            return
        choice = self.menu.handle_input(key)
        if choice is None:
            return
        option = MAIN_OPTIONS[choice]
        if option == "LEVEL UP":
            self._open_list("LEVEL_PICK", self._party_options())
            self.message = "Pick a creature to level up."
        elif option == "ADD CREATURE":
            self._open_list("ADD", self._species_options())
            self.message = f"LEFT/RIGHT: level ({self.add_level})   Z: add"
        elif option == "REMOVE CREATURE":
            self._open_list("REMOVE", self._party_options())
            self.message = "Z: remove (the last creature stays)."
        elif option == "ITEMS":
            self._open_list("ITEMS", self._item_options())
            self.message = "LEFT/RIGHT -1/+1  Z +10  DEL all"
        elif option == "MONEY":
            self.sub_menu = MenuBox(pygame.Rect(4, 22, 120, 98), MONEY_STEPS, visible_rows=5)
            self.page = "MONEY"
            self.message = f"Money: ${self._trainer.money}"
        elif option == "HEAL PARTY":
            self._trainer.party.heal_all()
            self.message = "Party fully healed."
        else:
            self._close()

    def _key_level_pick(self, key: int) -> None:
        if key in BACK:
            self.page = "MAIN"
            return
        choice = self.list_menu.handle_input(key)
        if choice is not None and choice < self._trainer.party.size:
            self.level_target = choice
            self.sub_menu = MenuBox(pygame.Rect(124, 22, 112, 66), LEVEL_STEPS, visible_rows=4)
            self.page = "LEVEL_AMOUNT"

    def _key_level_amount(self, key: int) -> None:
        if key in BACK:
            self._open_list("LEVEL_PICK", self._party_options(), keep_index=True)
            return
        choice = self.sub_menu.handle_input(key)
        if choice is None:
            return
        step = LEVEL_STEPS[choice]
        if step == "BACK":
            self._open_list("LEVEL_PICK", self._party_options(), keep_index=True)
            return
        mon = self._trainer.party.creatures[self.level_target]
        result = debug_tools.level_up(mon, int(step), self.engine.data_loader.get_move)
        learned = f" Learned {', '.join(result['learned'])}." if result["learned"] else ""
        evolve = " Ready to evolve!" if mon.can_evolve() else ""
        self.message = f"{mon.name} is now Lv{mon.level}.{learned}{evolve}"

    def _key_add(self, key: int) -> None:
        if key in BACK:
            self.page = "MAIN"
            return
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            delta = 1 if key in (pygame.K_RIGHT, pygame.K_d) else -1
            self.add_level = max(1, min(100, self.add_level + delta))
            self.message = f"LEFT/RIGHT: level ({self.add_level})   Z: add"
            return
        choice = self.list_menu.handle_input(key)
        if choice is None:
            return
        species = self.engine.data_loader.get_all_species()[choice]
        mon = self.engine.data_loader.get_creature(species["id"], level=self.add_level)
        where = debug_tools.add_creature(self._trainer, mon)
        self._state.pokedex.register_caught(mon.species_id)
        self.message = f"Added {mon.name} Lv{mon.level} to the {'party' if where == 'party' else 'PC box'}."

    def _key_remove(self, key: int) -> None:
        if key in BACK:
            self.page = "MAIN"
            return
        choice = self.list_menu.handle_input(key)
        if choice is None:
            return
        try:
            removed = debug_tools.remove_creature(self._trainer, choice)
            self.message = f"Removed {removed.name}."
        except RuleViolation as e:
            self.message = str(e) + "."
        self._open_list("REMOVE", self._party_options(), keep_index=True)

    def _key_items(self, key: int) -> None:
        if key in BACK:
            self.page = "MAIN"
            return
        index = self.list_menu.selected_index
        data = self.item_catalog[index]
        bag = self._trainer.bag
        if key in (pygame.K_RIGHT, pygame.K_d):
            bag.add(self.engine.data_loader.get_item(data["id"], 1), 1)
        elif key in (pygame.K_LEFT, pygame.K_a):
            bag.remove(data["id"], 1)
        elif key in CONFIRM:
            bag.add(self.engine.data_loader.get_item(data["id"], 10), 10)
        elif key == pygame.K_DELETE:
            bag.remove(data["id"], 10_000)
        else:
            self.list_menu.handle_input(key)
            return
        self._open_list("ITEMS", self._item_options(), keep_index=True)

    def _key_money(self, key: int) -> None:
        if key in BACK:
            self.page = "MAIN"
            return
        choice = self.sub_menu.handle_input(key)
        if choice is None:
            return
        step = MONEY_STEPS[choice]
        if step == "BACK":
            self.page = "MAIN"
            return
        amount = -self._trainer.money if step == "SET TO 0" else int(step)
        debug_tools.change_money(self._trainer, amount)
        self.message = f"Money: ${self._trainer.money}"

    def _close(self) -> None:
        """Leave the debug menu; creatures that reached their evolution level evolve now."""
        self.engine.pop_scene()
        ready = list(self._trainer.party.ready_to_evolve())
        if ready:
            from src.ui.evolution_scene import EvolutionScene
            self.engine.push_scene(EvolutionScene(self.engine, ready))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((48, 56, 72))
        draw_gba_panel(surface, pygame.Rect(4, 2, 232, 18))
        titles = {"MAIN": "DEBUG MENU", "LEVEL_PICK": "LEVEL UP", "LEVEL_AMOUNT": "LEVEL UP",
                  "ADD": "ADD CREATURE", "REMOVE": "REMOVE CREATURE", "ITEMS": "ITEMS", "MONEY": "MONEY"}
        draw_fitted_text(surface, titles[self.page], 12, 3, 140, self.font)
        draw_fitted_text(surface, f"${self._trainer.money}", 152, 6, 76, self.font_sm, align="right")

        if self.page == "MAIN":
            self.menu.draw(surface)
            panel = pygame.Rect(128, 22, 108, 98)
            draw_gba_panel(surface, panel)
            draw_fitted_text(surface, "PARTY", panel.x + 6, panel.y + 5, 96, self.font_sm)
            for i, c in enumerate(self._trainer.party.creatures):
                draw_fitted_text(surface, f"{c.name.upper()} Lv{c.level}", panel.x + 6,
                                 panel.y + 19 + i * 12, 96, self.font_sm)
        elif self.page in ("LEVEL_PICK", "ADD", "REMOVE", "ITEMS"):
            self.list_menu.draw(surface)
        elif self.page == "LEVEL_AMOUNT":
            self.list_menu.draw(surface)
            self.sub_menu.draw(surface)
        elif self.page == "MONEY":
            self.sub_menu.draw(surface)

        draw_gba_panel(surface, pygame.Rect(4, 124, 232, 32))
        for i, line in enumerate(wrap_text(self.message, 216, self.font_sm)[:2]):
            draw_fitted_text(surface, line, 12, 128 + 13 * i, 216, self.font_sm)
