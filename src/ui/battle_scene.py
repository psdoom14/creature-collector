"""GBA-style battle scene: draws the battle and plays back the model's BattleEvents."""
import pygame
from typing import List, Optional

from src.ui.scene import Scene
from src.ui.components import (
    draw_gba_panel,
    draw_gba_hp_box,
    draw_battle_platform,
    draw_crisp_text,
    HPBar,
    EXPBar,
    TextBox,
    MenuBox,
    get_font,
    COLOR_TEXT_DARK,
    COLOR_TEXT_SHADOW,
    TYPE_COLORS,
)
from src.ui.sprite_renderer import SpriteRenderer
from src.model.battle import Battle, BattleState, WildBattle
from src.model.events import BattleEvent, EventType
from src.model.creature import Creature

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)

# Events whose data carries a creature's new HP (target_uid / target_current_hp).
HP_EVENTS = (EventType.DAMAGE_DEALT, EventType.STATUS_DAMAGE, EventType.ITEM_USED, EventType.HEAL)


class BattleScene(Scene):
    """Complete GBA graphical battle scene."""

    def __init__(self, engine, wild_creature: Creature, battle: Optional[Battle] = None):
        super().__init__(engine)
        self.wild_creature = wild_creature
        self.battle: Battle = battle or WildBattle(
            player=self.engine.game_state.trainer,
            opponent=wild_creature,
            type_chart=self.engine.data_loader.get_type_chart(),
            move_source=self.engine.data_loader.get_move,
        )

        # UI Widgets
        self.textbox = TextBox(pygame.Rect(4, 110, 232, 46))
        self.action_menu = MenuBox(pygame.Rect(124, 110, 112, 46), ["FIGHT", "BAG", "POKÉMON", "RUN"], columns=2)
        self.move_menu: Optional[MenuBox] = None
        self.bag_menu: Optional[MenuBox] = None
        self.party_menu: Optional[MenuBox] = None
        self.learn_menu: Optional[MenuBox] = None
        self.party_menu_forced = False

        # HP Bars & EXP Bar
        self.wild_hp_bar = HPBar(x=20, y=24, width=64, height=5)
        self.player_hp_bar = HPBar(x=154, y=86, width=64, height=5)
        self.player_exp_bar = EXPBar(x=154, y=98, width=64, height=3)

        self.font = get_font(10)
        self.font_sm = get_font(8, "Silkscreen-Regular.ttf")

        # INTRO, DIALOGUE, ACTION_SELECT, MOVE_SELECT, BAG_SELECT, PARTY_SELECT, LEARN_SELECT, END
        self.sub_state = "INTRO"
        self.queued_events: List[BattleEvent] = []
        self.current_event: Optional[BattleEvent] = None

        # The player creature currently drawn. It changes only when a CREATURE_SENT
        # event is played, so the sprite doesn't swap before the "Go!" message.
        self.shown_creature: Optional[Creature] = self.battle.player_creature

        # Visual animation state
        self.enemy_shake_timer = 0.0
        self.player_shake_timer = 0.0
        self.enemy_y_offset = 0.0
        self.player_y_offset = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self, **kwargs) -> None:
        if self.sub_state != "INTRO":
            return
        self._show_player_creature(self.battle.player_creature)
        self.wild_hp_bar.set_hp(self.wild_creature.current_hp, self.wild_creature.max_hp, immediate=True)
        self.textbox.set_message(self.battle.intro_message)

    def _show_player_creature(self, creature: Optional[Creature]) -> None:
        self.shown_creature = creature
        self.player_y_offset = 0.0
        if creature:
            self.player_hp_bar.set_hp(creature.current_hp, creature.max_hp, immediate=True)
            self.player_exp_bar.set_ratio(creature.xp_progress, immediate=True)

    def _queue(self, events: List[BattleEvent]) -> None:
        self.queued_events.extend(events)
        self._play_next_event()

    # ------------------------------------------------------------------
    # Event playback
    # ------------------------------------------------------------------
    def _play_next_event(self) -> None:
        # Skip silent bookkeeping events (no text, e.g. the HP update after Recover).
        while self.queued_events and not self.queued_events[0].message:
            self._react_to(self.queued_events.pop(0))

        if not self.queued_events:
            self.current_event = None
            self._choose_next_state()
            return

        self.current_event = self.queued_events.pop(0)
        self.textbox.set_message(self.current_event.message)
        self.sub_state = "DIALOGUE"
        self._react_to(self.current_event)

    def _react_to(self, event: BattleEvent) -> None:
        """Animate sprites and bars for one event. Creatures are matched by uid, not name."""
        kind, data = event.event_type, event.data
        foe_uid = self.wild_creature.uid
        mine = self.shown_creature

        if kind in HP_EVENTS and "target_uid" in data:
            hp, max_hp = data["target_current_hp"], data["target_max_hp"]
            if data["target_uid"] == foe_uid:
                self.wild_hp_bar.set_hp(hp, max_hp)
                if kind is EventType.DAMAGE_DEALT:
                    self.enemy_shake_timer = 0.3
            elif mine and data["target_uid"] == mine.uid:
                self.player_hp_bar.set_hp(hp, max_hp)
                if kind is EventType.DAMAGE_DEALT:
                    self.player_shake_timer = 0.3

        elif kind is EventType.FAINTED:
            if data.get("uid") == foe_uid:
                self.enemy_y_offset = 30.0
            elif mine and data.get("uid") == mine.uid:
                self.player_y_offset = 40.0

        elif kind is EventType.CREATURE_SENT:
            self._show_player_creature(self.battle.player_creature)

        elif kind is EventType.CAUGHT:
            self.engine.game_state.pokedex.register_caught(self.wild_creature.species_id)

        elif kind in (EventType.XP_GAINED, EventType.LEVEL_UP) and mine:
            if kind is EventType.LEVEL_UP:
                self.player_hp_bar.set_hp(mine.current_hp, mine.max_hp)
            self.player_exp_bar.set_ratio(mine.xp_progress)

    def _choose_next_state(self) -> None:
        """All events shown: decide what the player does next."""
        if self.battle.pending_move is not None:
            self._open_learn_menu()
        elif self.battle.state is BattleState.SELECTING_SWITCH:
            self._open_party_menu(forced=True)
        elif not self.battle.is_active:
            self.sub_state = "END"
            self.textbox.set_message("Press Enter to continue.")
        else:
            self.sub_state = "ACTION_SELECT"

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------
    def _open_party_menu(self, forced: bool) -> None:
        options = []
        for c in self.battle.player.party:
            hp = "FAINTED" if c.is_fainted else f"{c.current_hp}/{c.max_hp}"
            options.append(f"{c.name.upper()[:10]:<10} L{c.level:<3} {hp}")
        self.party_menu = MenuBox(pygame.Rect(36, 6, 200, 100), options, columns=1,
                                  visible_rows=6)
        self.party_menu_forced = forced
        self.textbox.set_message("Choose the next creature!" if forced else "Switch to which creature?")
        self.textbox.advance()  # show instantly
        self.sub_state = "PARTY_SELECT"

    def _open_learn_menu(self) -> None:
        learner, move = self.battle.pending_learner, self.battle.pending_move
        options = [m.name for m in learner.moves] + ["DON'T LEARN"]
        self.learn_menu = MenuBox(pygame.Rect(124, 6, 112, 70), options, columns=1,
                                  visible_rows=5)
        self.textbox.set_message(f"Forget a move to learn {move.name}?")
        self.textbox.advance()
        self.sub_state = "LEARN_SELECT"

    def _open_bag_menu(self) -> None:
        items = self.battle.player.bag.items
        if not items:
            self.textbox.set_message("The bag is empty!")
            self.sub_state = "DIALOGUE"
            return
        names = [f"{it.name[:12]} x{it.quantity}" for it in items]
        self.bag_menu = MenuBox(pygame.Rect(80, 110, 156, 46), names, columns=1, visible_rows=3)
        self.sub_state = "BAG_SELECT"

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        handler = getattr(self, f"_input_{self.sub_state.lower()}", None)
        if handler:
            handler(key)

    def _input_intro(self, key: int) -> None:
        if key not in CONFIRM_KEYS:
            return
        if not self.textbox.is_finished_typing:
            self.textbox.advance()
            return
        lead = self.battle.player_creature
        self.textbox.set_message(f"Go! {lead.name}!" if lead else "...")
        self.sub_state = "DIALOGUE"

    def _input_dialogue(self, key: int) -> None:
        if key in CONFIRM_KEYS and not self.textbox.advance():
            self._play_next_event()

    def _input_action_select(self, key: int) -> None:
        choice = self.action_menu.handle_input(key)
        if choice == 0:  # FIGHT
            lead = self.battle.player_creature
            self.move_menu = MenuBox(pygame.Rect(4, 110, 156, 46),
                                     [m.name[:10] for m in lead.moves], columns=2)
            self.sub_state = "MOVE_SELECT"
        elif choice == 1:  # BAG
            self._open_bag_menu()
        elif choice == 2:  # POKÉMON
            self._open_party_menu(forced=False)
        elif choice == 3:  # RUN
            self._queue(self.battle.attempt_run())

    def _input_move_select(self, key: int) -> None:
        if key in CANCEL_KEYS:
            self.sub_state = "ACTION_SELECT"
            return
        choice = self.move_menu.handle_input(key)
        if choice is not None:
            self._queue(self.battle.execute_move(choice))

    def _input_bag_select(self, key: int) -> None:
        if key in CANCEL_KEYS:
            self.sub_state = "ACTION_SELECT"
            return
        choice = self.bag_menu.handle_input(key)
        items = self.battle.player.bag.items
        if choice is not None and 0 <= choice < len(items):
            # Polymorphic: each Item subclass decides what using it in battle means.
            self._queue(self.battle.use_item(items[choice].id))

    def _input_party_select(self, key: int) -> None:
        if key in CANCEL_KEYS and not self.party_menu_forced:
            self.sub_state = "ACTION_SELECT"
            return
        choice = self.party_menu.handle_input(key)
        if choice is None:
            return
        events = self.battle.switch_creature(choice)
        if events and events[0].event_type is EventType.INVALID_ACTION:
            # Stay in the menu and explain why.
            self.textbox.set_message(events[0].message)
            self.textbox.advance()
            return
        self._queue(events)

    def _input_learn_select(self, key: int) -> None:
        choice = self.learn_menu.handle_input(key)
        if key in CANCEL_KEYS:
            choice = len(self.learn_menu.options) - 1
        if choice is None:
            return
        learner = self.battle.pending_learner
        slot = choice if choice < len(learner.moves) else None
        self._queue(self.battle.learn_pending_move(slot))

    def _input_end(self, key: int) -> None:
        if key not in CONFIRM_KEYS:
            return
        engine = self.engine
        trainer = engine.game_state.trainer
        lost = self.battle.state is BattleState.LOST
        engine.pop_scene()

        if lost:
            money_lost = trainer.black_out()
            overworld = engine.current_scene
            if hasattr(overworld, "respawn_after_blackout"):
                overworld.respawn_after_blackout(money_lost)
            return

        ready = list(trainer.party.ready_to_evolve())
        if ready:
            from src.ui.evolution_scene import EvolutionScene
            engine.push_scene(EvolutionScene(engine, ready))

    # ------------------------------------------------------------------
    # Update / draw
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.wild_hp_bar.update(dt)
        self.player_hp_bar.update(dt)
        self.player_exp_bar.update(dt)
        self.textbox.update(dt)
        self.enemy_shake_timer = max(0.0, self.enemy_shake_timer - dt)
        self.player_shake_timer = max(0.0, self.player_shake_timer - dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((232, 240, 224))

        draw_battle_platform(surface, center_x=181, center_y=60, width=88, height=26, is_player=False)
        draw_battle_platform(surface, center_x=58, center_y=108, width=108, height=30, is_player=True)

        # Opponent sprite (top right) and info card (top left)
        e_shake_x = 3 if self.enemy_shake_timer > 0 and int(self.enemy_shake_timer * 30) % 2 == 0 else 0
        if self.enemy_y_offset < 30:
            enemy_surf = SpriteRenderer.get_creature_sprite(
                self.wild_creature.species_id, self.wild_creature.name,
                self.wild_creature.primary_type, is_back=False, size=(52, 52))
            surface.blit(enemy_surf, (155 + e_shake_x, 20 + self.enemy_y_offset))
        draw_gba_hp_box(
            surface, pygame.Rect(10, 10, 105, 32),
            name=self.wild_creature.name, level=self.wild_creature.level,
            current_hp=self.wild_hp_bar.display_hp * self.wild_creature.max_hp,
            max_hp=self.wild_creature.max_hp, exp_ratio=None,
            status=self.wild_creature.status_effect,
        )

        # Player sprite (bottom left, back view) and info card (bottom right)
        mine = self.shown_creature
        if mine and self.player_y_offset < 40:
            p_shake_x = 3 if self.player_shake_timer > 0 and int(self.player_shake_timer * 30) % 2 == 0 else 0
            player_surf = SpriteRenderer.get_creature_sprite(
                mine.species_id, mine.name, mine.primary_type, is_back=True, size=(56, 56))
            surface.blit(player_surf, (30 + p_shake_x, 62 + self.player_y_offset))
        if mine:
            draw_gba_hp_box(
                surface, pygame.Rect(122, 64, 114, 42),
                name=mine.name, level=mine.level,
                current_hp=self.player_hp_bar.display_hp * mine.max_hp,
                max_hp=mine.max_hp, exp_ratio=self.player_exp_bar.display_ratio,
                status=mine.status_effect,
            )

        # Bottom controls
        if self.sub_state == "ACTION_SELECT":
            draw_gba_panel(surface, pygame.Rect(4, 110, 116, 46))
            draw_crisp_text(surface, "What will you do?", 12, 126, self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
            self.action_menu.draw(surface)
        elif self.sub_state == "MOVE_SELECT" and self.move_menu:
            self.move_menu.draw(surface)
            lead = self.battle.player_creature
            if lead and 0 <= self.move_menu.selected_index < len(lead.moves):
                sel_move = lead.moves[self.move_menu.selected_index]
                draw_gba_panel(surface, pygame.Rect(162, 110, 74, 46))
                draw_crisp_text(surface, "TYPE/", 168, 116, self.font_sm, (96, 104, 120), COLOR_TEXT_SHADOW)
                type_col = TYPE_COLORS.get(sel_move.type, COLOR_TEXT_DARK)
                draw_crisp_text(surface, sel_move.type.upper(), 172, 126, self.font_sm, type_col, COLOR_TEXT_SHADOW)
                draw_crisp_text(surface, f"PP {sel_move.current_pp}/{sel_move.max_pp}", 168, 140,
                                self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
        elif self.sub_state == "BAG_SELECT" and self.bag_menu:
            draw_gba_panel(surface, pygame.Rect(4, 110, 72, 46))
            draw_crisp_text(surface, "Use Item:", 10, 126, self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
            self.bag_menu.draw(surface)
        elif self.sub_state == "PARTY_SELECT" and self.party_menu:
            self.party_menu.draw(surface)
            self.textbox.draw(surface)
        elif self.sub_state == "LEARN_SELECT" and self.learn_menu:
            self.learn_menu.draw(surface)
            self.textbox.draw(surface)
        else:
            self.textbox.draw(surface)
