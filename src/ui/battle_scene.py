"""GBA-style visual Battle Scene rendering combat, HP bars, battle pedestals, animations, and menus."""
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
    COLOR_PANEL_BG,
    TYPE_COLORS,
    STATUS_COLORS,
)
from src.ui.sprite_renderer import SpriteRenderer
from src.model.battle import Battle, BattleState, BattleEvent
from src.model.creature import Creature
from src.model.item import CatchBall


class BattleScene(Scene):
    """Complete GBA graphical battle scene."""

    def __init__(self, engine, wild_creature: Creature):
        super().__init__(engine)
        self.wild_creature = wild_creature
        self.battle = Battle(
            player=self.engine.game_state.trainer,
            wild_creature=self.wild_creature,
            type_chart=self.engine.data_loader.get_type_chart(),
        )

        # UI Widgets
        self.textbox = TextBox(pygame.Rect(4, 110, 232, 46))
        self.action_menu = MenuBox(pygame.Rect(124, 110, 112, 46), ["FIGHT", "BAG", "POKÉMON", "RUN"], columns=2)
        self.move_menu: Optional[MenuBox] = None
        self.bag_menu: Optional[MenuBox] = None

        # HP Bars & EXP Bar
        self.wild_hp_bar = HPBar(x=20, y=24, width=64, height=5)
        self.player_hp_bar = HPBar(x=154, y=86, width=64, height=5)
        self.player_exp_bar = EXPBar(x=154, y=98, width=64, height=3)

        self.font = get_font(10)
        self.font_sm = get_font(8, "Silkscreen-Regular.ttf")

        # Internal Scene Sub-State
        self.sub_state = "INTRO"  # INTRO, DIALOGUE, ACTION_SELECT, MOVE_SELECT, BAG_SELECT, END
        self.queued_events: List[BattleEvent] = []
        self.current_event: Optional[BattleEvent] = None

        # Visual animation timers
        self.enemy_shake_timer = 0.0
        self.player_shake_timer = 0.0
        self.enemy_y_offset = 0.0

    def on_enter(self, **kwargs) -> None:
        p_lead = self.battle.player_creature
        if p_lead:
            self.player_hp_bar.set_hp(p_lead.current_hp, p_lead.max_hp, immediate=True)
            cur_xp = p_lead.level ** 3
            nxt_xp = (p_lead.level + 1) ** 3
            span = max(1, nxt_xp - cur_xp)
            exp_ratio = max(0.0, min(1.0, (p_lead.xp - cur_xp) / span))
            if p_lead.level >= 100:
                exp_ratio = 1.0
            self.player_exp_bar.set_ratio(exp_ratio, immediate=True)

        self.wild_hp_bar.set_hp(self.wild_creature.current_hp, self.wild_creature.max_hp, immediate=True)

        self.textbox.set_message(f"Wild {self.wild_creature.name} appeared!")
        self.sub_state = "INTRO"

    def _play_next_event(self) -> None:
        if self.queued_events:
            self.current_event = self.queued_events.pop(0)
            self.textbox.set_message(self.current_event.message)
            self.sub_state = "DIALOGUE"

            # Trigger sprite reactions based on event type
            if self.current_event.event_type == "damage_dealt":
                target = self.current_event.data.get("target")
                if target == self.wild_creature.name:
                    self.enemy_shake_timer = 0.3
                    self.wild_hp_bar.set_hp(self.wild_creature.current_hp, self.wild_creature.max_hp)
                elif self.battle.player_creature and target == self.battle.player_creature.name:
                    self.player_shake_timer = 0.3
                    self.player_hp_bar.set_hp(self.battle.player_creature.current_hp, self.battle.player_creature.max_hp)

            elif self.current_event.event_type == "fainted":
                fainted = self.current_event.data.get("fainted")
                if fainted == self.wild_creature.name:
                    self.enemy_y_offset = 30.0  # drop down

            elif self.current_event.event_type == "caught":
                self.engine.game_state.pokedex.register_caught(self.wild_creature.species_id)

            # Update EXP bar if player creature gained XP
            if p_lead := self.battle.player_creature:
                cur_xp = p_lead.level ** 3
                nxt_xp = (p_lead.level + 1) ** 3
                span = max(1, nxt_xp - cur_xp)
                exp_ratio = max(0.0, min(1.0, (p_lead.xp - cur_xp) / span))
                if p_lead.level >= 100:
                    exp_ratio = 1.0
                self.player_exp_bar.set_ratio(exp_ratio)
        else:
            self.current_event = None
            if not self.battle.is_active:
                self.sub_state = "END"
                self.textbox.set_message("Press Enter to return.")
            else:
                self.sub_state = "ACTION_SELECT"

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        key = event.key

        if self.sub_state == "INTRO":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                p_lead = self.battle.player_creature
                if p_lead:
                    self.textbox.set_message(f"Go! {p_lead.name}!")
                    self.sub_state = "DIALOGUE"
                else:
                    self.sub_state = "ACTION_SELECT"

        elif self.sub_state == "DIALOGUE":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                if not self.textbox.advance():
                    self._play_next_event()

        elif self.sub_state == "ACTION_SELECT":
            choice = self.action_menu.handle_input(key)
            if choice is not None:
                if choice == 0:  # FIGHT
                    p_lead = self.battle.player_creature
                    if p_lead:
                        move_names = [f"{m.name[:10]}" for m in p_lead.moves]
                        self.move_menu = MenuBox(pygame.Rect(4, 110, 156, 46), move_names, columns=2)
                        self.sub_state = "MOVE_SELECT"
                elif choice == 1:  # BAG
                    items = list(self.battle.player.inventory.values())
                    if items:
                        item_names = [f"{it.name[:12]} x{it.quantity}" for it in items[:4]]
                        self.bag_menu = MenuBox(pygame.Rect(80, 110, 156, 46), item_names, columns=1)
                        self.sub_state = "BAG_SELECT"
                    else:
                        self.textbox.set_message("Bag is empty!")
                        self.sub_state = "DIALOGUE"
                elif choice == 2:  # POKEMON
                    self.textbox.set_message(f"{self.battle.player_creature.name} is already fighting!")
                    self.sub_state = "DIALOGUE"
                elif choice == 3:  # RUN
                    events = self.battle.attempt_run()
                    self.queued_events.extend(events)
                    self._play_next_event()

        elif self.sub_state == "MOVE_SELECT":
            if key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE):
                self.sub_state = "ACTION_SELECT"
            elif self.move_menu:
                m_choice = self.move_menu.handle_input(key)
                if m_choice is not None:
                    events = self.battle.execute_move(m_choice)
                    self.queued_events.extend(events)
                    self._play_next_event()

        elif self.sub_state == "BAG_SELECT":
            if key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE):
                self.sub_state = "ACTION_SELECT"
            elif self.bag_menu:
                b_choice = self.bag_menu.handle_input(key)
                if b_choice is not None:
                    items = list(self.battle.player.inventory.values())
                    if 0 <= b_choice < len(items):
                        it = items[b_choice]
                        if isinstance(it, CatchBall):
                            events = self.battle.attempt_catch(it.id)
                            self.queued_events.extend(events)
                            self._play_next_event()
                        else:
                            msg = self.battle.player.use_item(it.id, self.battle.player_creature)
                            self.queued_events.append(BattleEvent("item_used", msg))
                            self._play_next_event()

        elif self.sub_state == "END":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                self.engine.pop_scene()

    def update(self, dt: float) -> None:
        self.wild_hp_bar.update(dt)
        self.player_hp_bar.update(dt)
        self.player_exp_bar.update(dt)
        self.textbox.update(dt)

        if self.enemy_shake_timer > 0:
            self.enemy_shake_timer = max(0.0, self.enemy_shake_timer - dt)
        if self.player_shake_timer > 0:
            self.player_shake_timer = max(0.0, self.player_shake_timer - dt)

    def draw(self, surface: pygame.Surface) -> None:
        # Background: GBA classic duel background
        surface.fill((232, 240, 224))

        # Ground pedestals (3D tiered grass/dirt battle platforms)
        draw_battle_platform(surface, center_x=181, center_y=60, width=88, height=26, is_player=False)
        draw_battle_platform(surface, center_x=58, center_y=108, width=108, height=30, is_player=True)

        # Enemy Creature Sprite (top right)
        e_shake_x = 3 if self.enemy_shake_timer > 0 and int(self.enemy_shake_timer * 30) % 2 == 0 else 0
        enemy_surf = SpriteRenderer.get_creature_sprite(
            self.wild_creature.species_id,
            self.wild_creature.name,
            self.wild_creature.primary_type,
            is_back=False,
            size=(52, 52),
        )
        surface.blit(enemy_surf, (155 + e_shake_x, 20 + self.enemy_y_offset))

        # Enemy Info Card (top left)
        draw_gba_hp_box(
            surface,
            pygame.Rect(10, 10, 105, 32),
            name=self.wild_creature.name,
            level=self.wild_creature.level,
            current_hp=self.wild_hp_bar.display_hp * self.wild_creature.max_hp,
            max_hp=self.wild_creature.max_hp,
            exp_ratio=None,
            status=self.wild_creature.status_effect,
        )

        # Player Creature Sprite (bottom left back view)
        p_lead = self.battle.player_creature
        if p_lead:
            p_shake_x = 3 if self.player_shake_timer > 0 and int(self.player_shake_timer * 30) % 2 == 0 else 0
            player_surf = SpriteRenderer.get_creature_sprite(
                p_lead.species_id,
                p_lead.name,
                p_lead.primary_type,
                is_back=True,
                size=(56, 56),
            )
            surface.blit(player_surf, (30 + p_shake_x, 62))

            # Player Info Card (bottom right)
            draw_gba_hp_box(
                surface,
                pygame.Rect(122, 64, 114, 42),
                name=p_lead.name,
                level=p_lead.level,
                current_hp=self.player_hp_bar.display_hp * p_lead.max_hp,
                max_hp=p_lead.max_hp,
                exp_ratio=self.player_exp_bar.display_ratio,
                status=p_lead.status_effect,
            )

        # Bottom UI Controls
        if self.sub_state == "ACTION_SELECT":
            draw_gba_panel(surface, pygame.Rect(4, 110, 116, 46))
            draw_crisp_text(surface, "What will you do?", 12, 126, self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
            self.action_menu.draw(surface)
        elif self.sub_state == "MOVE_SELECT" and self.move_menu:
            self.move_menu.draw(surface)
            p_lead = self.battle.player_creature
            if p_lead and 0 <= self.move_menu.selected_index < len(p_lead.moves):
                sel_move = p_lead.moves[self.move_menu.selected_index]
                draw_gba_panel(surface, pygame.Rect(162, 110, 74, 46))
                draw_crisp_text(surface, "TYPE/", 168, 116, self.font_sm, (96, 104, 120), COLOR_TEXT_SHADOW)
                type_col = TYPE_COLORS.get(sel_move.type, COLOR_TEXT_DARK)
                draw_crisp_text(surface, sel_move.type.upper(), 172, 126, self.font_sm, type_col, COLOR_TEXT_SHADOW)
                draw_crisp_text(surface, f"PP {sel_move.current_pp}/{sel_move.max_pp}", 168, 140, self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
        elif self.sub_state == "BAG_SELECT" and self.bag_menu:
            draw_gba_panel(surface, pygame.Rect(4, 110, 72, 46))
            draw_crisp_text(surface, "Use Item:", 10, 126, self.font_sm, COLOR_TEXT_DARK, COLOR_TEXT_SHADOW)
            self.bag_menu.draw(surface)
        else:
            self.textbox.draw(surface)
