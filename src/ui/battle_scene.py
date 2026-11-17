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
from src.ui import animations as A
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
        # The opposing creature currently drawn. In trainer battles it changes when an
        # OPPONENT_SENT event is played (not before, so the sprite swaps with the message).
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

        # Running animations (see src/ui/animations.py). The scene only calls their
        # update / modify / draw methods; each subclass decides what it looks like.
        self.layout = A.BattleLayout()
        self.anims: List[A.Animation] = []
        self.player_out = False          # the player's creature appears with "Go!"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self, **kwargs) -> None:
        if self.sub_state != "INTRO" or self.anims:
            return
        self._show_player_creature(self.battle.player_creature)
        self.wild_hp_bar.set_hp(self.wild_creature.current_hp, self.wild_creature.max_hp, immediate=True)
        self.textbox.set_message(self.battle.intro_message)
        self._animate(A.SlideIn(A.FOE))
        self._animate(A.SlideIn(A.PLAYER))   # the player's (still empty) platform

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------
    @property
    def is_animating(self) -> bool:
        """True while an animation the player must wait for is still running."""
        return any(a.blocking and not a.done for a in self.anims)

    @property
    def foe_in_ball(self) -> bool:
        """The wild creature is inside a thrown ball (not drawn)."""
        return any(getattr(a, "holds_foe", False) for a in self.anims)

    def _animate(self, anim: A.Animation) -> None:
        self.anims.append(anim)

    def _forget(self, side: str) -> None:
        """Drop lingering animations for a side (a fainted sprite, a held ball) before a new creature appears."""
        self.anims = [a for a in self.anims if a.side != side or not a.done]

    def _side_of(self, uid) -> Optional[str]:
        if uid == self.wild_creature.uid:
            return A.FOE
        if self.shown_creature and uid == self.shown_creature.uid:
            return A.PLAYER
        return None

    def _show_player_creature(self, creature: Optional[Creature]) -> None:
        self.shown_creature = creature
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
            side = self._side_of(data["target_uid"])
            if side == A.FOE:
                self.wild_hp_bar.set_hp(hp, max_hp)
            elif side == A.PLAYER:
                self.player_hp_bar.set_hp(hp, max_hp)
            if side and kind is EventType.DAMAGE_DEALT:
                self._animate(A.HitBlink(side))
            elif side and kind in (EventType.ITEM_USED, EventType.HEAL) and event.message:
                self._animate(A.HealSparkle(side))

        elif kind is EventType.MOVE_USED:
            attacker = self._side_of(data.get("user_uid")) or A.PLAYER
            self._animate(A.MoveAnimation.create(data.get("type", "Normal"),
                                                 data.get("category", "physical"), attacker))

        elif kind is EventType.CRITICAL or (kind is EventType.EFFECTIVENESS
                                             and data.get("multiplier", 1) > 1):
            self._animate(A.ScreenShake())

        elif kind is EventType.FAINTED:
            side = self._side_of(data.get("uid"))
            if side:
                self._animate(A.FaintDrop(side))

        elif kind is EventType.CREATURE_SENT:
            self._show_player_creature(self.battle.player_creature)
            self._forget(A.PLAYER)
            self.player_out = True
            self._animate(A.SendOut(A.PLAYER))

        elif kind is EventType.OPPONENT_SENT:
            self.wild_creature = self.battle.opponent
            self.wild_hp_bar.set_hp(self.wild_creature.current_hp, self.wild_creature.max_hp, immediate=True)
            self.engine.game_state.pokedex.register_seen(self.wild_creature.species_id)
            self._forget(A.FOE)
            self._animate(A.SendOut(A.FOE))

        elif kind is EventType.BALL_THROWN:
            self._animate(A.BallThrow())

        elif kind in (EventType.CAUGHT, EventType.CATCH_FAILED):
            self.anims = [a for a in self.anims if not getattr(a, "holds_foe", False)]
            caught = kind is EventType.CAUGHT
            self._animate(A.BallWobble(shakes=data.get("shakes", 0), caught=caught))
            if caught:
                self.engine.game_state.pokedex.register_caught(self.wild_creature.species_id)

        elif kind is EventType.STATUS_APPLIED:
            side = self._side_of(data.get("target_uid"))
            if side:
                self._animate(A.StatusSparkle(side, data.get("status", "")))

        elif kind is EventType.STAT_CHANGE:
            side = self._side_of(data.get("target_uid"))
            if side:
                self._animate(A.StatArrows(side, rising=data.get("change", 0) > 0))

        elif kind in (EventType.XP_GAINED, EventType.LEVEL_UP) and mine:
            if kind is EventType.LEVEL_UP:
                self.player_hp_bar.set_hp(mine.current_hp, mine.max_hp)
                self._animate(A.LevelUpGlow(A.PLAYER))
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
        if self.is_animating:
            return  # wait for the animation, as on the GBA
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
        if lead:
            self.player_out = True
            self._animate(A.SendOut(A.PLAYER))

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

        overworld = engine.current_scene
        if hasattr(overworld, "on_battle_end"):
            overworld.on_battle_end(self.battle)

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
        for anim in self.anims:
            anim.update(dt)
        # Finished animations go, except those that leave a lasting look (a fainted
        # sprite stays down, a caught creature stays in its ball) until replaced.
        self.anims = [a for a in self.anims if not a.done or getattr(a, "persist", False)]

    def _mods(self, side: str) -> A.SpriteMods:
        mods = A.SpriteMods()
        for anim in self.anims:
            anim.modify(side, mods)   # polymorphic: each animation changes the sprite its own way
        return mods

    def _intro_dx(self, side: str) -> float:
        """How far the intro slide-in still has to move this side's platform."""
        mods = A.SpriteMods()
        for anim in self.anims:
            if getattr(anim, "hides_hud", False):
                anim.modify(side, mods)
        return mods.dx

    def _draw_creature(self, surface, sprite: pygame.Surface, side: str, top_left, ground_y: int) -> None:
        mods = self._mods(side)
        if not mods.visible:
            return
        img = sprite
        if mods.scale != 1.0:
            w = max(1, int(sprite.get_width() * mods.scale))
            h = max(1, int(sprite.get_height() * mods.scale))
            img = pygame.transform.scale(sprite, (w, h))
        if mods.white > 0:
            img = img.copy()
            level = int(255 * min(1.0, mods.white))
            img.fill((level, level, level, 0), special_flags=pygame.BLEND_RGBA_ADD)
        cx = top_left[0] + sprite.get_width() / 2 + mods.dx
        bottom = top_left[1] + sprite.get_height() + mods.dy
        pos = (int(cx - img.get_width() / 2), int(bottom - img.get_height()))
        if mods.sink:  # disappear behind the platform edge
            surface.set_clip(pygame.Rect(0, 0, surface.get_width(), ground_y))
        surface.blit(img, pos)
        surface.set_clip(None)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((232, 240, 224))

        # Platforms slide in with the intro, like the creature standing on them
        draw_battle_platform(surface, center_x=181 + int(self._intro_dx(A.FOE)), center_y=60,
                             width=88, height=26, is_player=False)
        draw_battle_platform(surface, center_x=58 + int(self._intro_dx(A.PLAYER)), center_y=108,
                             width=108, height=30, is_player=True)

        # Opponent sprite (top right)
        enemy_surf = SpriteRenderer.get_creature_sprite(
            self.wild_creature.species_id, self.wild_creature.name,
            self.wild_creature.primary_type, is_back=False, size=(52, 52))
        self._draw_creature(surface, enemy_surf, A.FOE, (155, 20), ground_y=72)

        # Player sprite (bottom left, back view)
        mine = self.shown_creature
        if mine and self.player_out:
            player_surf = SpriteRenderer.get_creature_sprite(
                mine.species_id, mine.name, mine.primary_type, is_back=True, size=(56, 56))
            self._draw_creature(surface, player_surf, A.PLAYER, (30, 62), ground_y=118)

        # Effects (move particles, the ball, sparkles) over the sprites
        for anim in self.anims:
            anim.draw(surface, self.layout)

        # Info cards
        intro_sliding = any(getattr(a, "hides_hud", False) and not a.done for a in self.anims)
        if not intro_sliding:
            draw_gba_hp_box(
                surface, pygame.Rect(10, 10, 105, 32),
                name=self.wild_creature.name, level=self.wild_creature.level,
                current_hp=self.wild_hp_bar.display_hp * self.wild_creature.max_hp,
                max_hp=self.wild_creature.max_hp, exp_ratio=None,
                status=self.wild_creature.status_effect,
            )
        if mine and self.player_out:
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
