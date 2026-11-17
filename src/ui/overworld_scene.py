"""Overworld screen: walking around the world, talking to people, warps and wild encounters.

The rules (what blocks you, where warps go, who you talk to, where wild creatures
appear) live in the model's ``Explorer``. This scene only animates and draws.

Controls: arrows/WASD walk, Z/Space talk or read, Enter/Esc open the menu.
"""
import random
from typing import List, Optional, Tuple

import pygame

from src.model.direction import Direction
from src.model.errors import SaveError
from src.model.entities import StarterBall, TrainerNPC
from src.model.story import give_starter, pick_rival_starter
from src.model.world import Explorer, Location, StepResult
from src.save_manager import SaveManager
from src.ui.bag_scene import BagScene
from src.ui.card_scene import CardScene
from src.ui.battle_scene import BattleScene
from src.ui.components import (
    MenuBox, TextBox, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text,
)
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene
from src.ui.scene import Scene
from src.ui.sprite_renderer import SpriteRenderer
from src.ui.transitions import TrainerTransition, Transition, TransitionScene, WildTransition
from src.ui.world_renderer import TILE, CharacterSprites, MapRenderer

RIVAL_NAME = "JUNO"

TALK_KEYS = (pygame.K_z, pygame.K_SPACE)
MENU_KEYS = (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_TAB)
CANCEL_KEYS = (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)
ADVANCE_KEYS = (pygame.K_z, pygame.K_SPACE, pygame.K_RETURN, pygame.K_x)
MOVE_KEYS = {
    pygame.K_UP: Direction.UP, pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN, pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT, pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT, pygame.K_d: Direction.RIGHT,
}


class OverworldScene(Scene):
    """Modes: WALK (free movement), DIALOGUE (text box open), MENU (pause menu open),
    CONFIRM_STARTER (YES/NO over a starter ball), SPOTTED (a trainer just saw you: "!")."""

    SPOTTED_SECONDS = 0.7

    STEP_SECONDS = 0.20
    FADE_SECONDS = 0.18
    LOCATION_BANNER_SECONDS = 2.5
    WATER_FRAME_SECONDS = 0.25

    def __init__(self, engine, rng: Optional[random.Random] = None):
        super().__init__(engine)
        self.rng = rng or random.Random()
        state = engine.game_state
        start = state.location or engine.data_loader.start_location()
        facing = state.facing if state.location else engine.data_loader.start_facing()
        self.explorer = Explorer(engine.world, start, facing, flags=state.flags)
        self.renderer = MapRenderer(self.explorer.current_map)

        self.font = get_font(10)
        self.font_sm = small_font()
        self.mode = "WALK"
        self.held_direction: Optional[Direction] = None

        # Step animation: the sprite slides from step_from to the current tile
        self.step_timer = 0.0
        self.step_from: Optional[Tuple[int, int]] = None
        self.walk_frame = 0
        # Warp fade: 0 = clear, 1 = black; fade_dir +1 fading out, -1 fading in
        self.fade = 0.0
        self.fade_dir = 0
        self._pending_map_change = False
        self._last_frame: Optional[pygame.Surface] = None  # shown while fading out of a map

        self.water_timer = 0.0
        self.water_frame = 0

        self.pause_menu = MenuBox(pygame.Rect(150, 8, 84, 88),
                                  ["POKÉDEX", "PARTY", "BAG", "CARD", "SAVE", "EXIT"])
        self.textbox = TextBox(pygame.Rect(4, 110, 232, 46))
        self.dialogue: List[str] = []
        self.starter_menu = MenuBox(pygame.Rect(180, 64, 56, 42), ["YES", "NO"])
        self.offered_species: Optional[int] = None
        # Something to do when the current dialogue closes (e.g. start a trainer battle)
        self._after_dialogue = None
        self.spotter: Optional[TrainerNPC] = None
        self.spotted_timer = 0.0

        self.notification_text: Optional[str] = None
        self.notification_timer = 0.0
        self.location_timer = 0.0
        self._sync_location_name()
        self.show_location_banner()

    # ------------------------------------------------------------------
    # Position helpers (also used by tests and the screenshot script)
    # ------------------------------------------------------------------
    @property
    def player_x(self) -> int:
        return self.explorer.location.x

    @player_x.setter
    def player_x(self, value: int) -> None:
        loc = self.explorer.location
        self.explorer.teleport(Location(loc.map_id, value, loc.y))

    @property
    def player_y(self) -> int:
        return self.explorer.location.y

    @player_y.setter
    def player_y(self, value: int) -> None:
        loc = self.explorer.location
        self.explorer.teleport(Location(loc.map_id, loc.x, value))

    @property
    def is_moving(self) -> bool:
        return self.step_from is not None

    def teleport(self, location: Location, facing: Direction) -> None:
        """Jump straight to ``location`` (redraws the map if it changed)."""
        old_map = self.explorer.location.map_id
        self.explorer.teleport(location, facing)
        self.step_from = None
        if location.map_id != old_map:
            self._on_map_changed()

    def _on_map_changed(self) -> None:
        self.renderer = MapRenderer(self.explorer.current_map)
        self._sync_location_name()
        self.show_location_banner()

    @property
    def allows_debug(self) -> bool:
        """The debug menu (F1) may open only while freely walking."""
        return self.mode == "WALK" and not self.is_moving and self.fade_dir == 0

    def _sync_location_name(self) -> None:
        self.engine.game_state.current_route = self.explorer.current_map.name

    # ------------------------------------------------------------------
    # Banner, notifications, saving, blackout
    # ------------------------------------------------------------------
    @property
    def location_banner_visible(self) -> bool:
        return self.location_timer > 0

    def show_location_banner(self) -> None:
        self.location_timer = self.LOCATION_BANNER_SECONDS

    def show_notification(self, text: str, duration: float = 2.0) -> None:
        self.notification_text = text
        self.notification_timer = duration

    def save_game(self) -> bool:
        """Save to disk. Returns False (and keeps the old save) if writing fails."""
        state = self.engine.game_state
        state.location = self.explorer.location
        state.facing = self.explorer.facing
        try:
            return SaveManager.save_game(state, self.engine.save_path)
        except SaveError:
            return False

    def respawn_after_blackout(self, money_lost: int) -> None:
        """After a lost battle (party already healed by Trainer.black_out())."""
        state = self.engine.game_state
        target = state.respawn_location or self.engine.data_loader.start_location()
        self.teleport(target, Direction.UP if state.respawn_location else Direction.DOWN)
        self.mode = "WALK"
        self.show_notification(f"Blacked out! Lost ${money_lost}", 3.0)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            if MOVE_KEYS.get(event.key) == self.held_direction:
                self.held_direction = None
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key

        if self.mode == "DIALOGUE":
            if key in ADVANCE_KEYS:
                self._advance_dialogue()
        elif self.mode == "CONFIRM_STARTER":
            self._handle_starter_key(key)
        elif self.mode == "SPOTTED":
            return
        elif self.mode == "MENU":
            self._handle_menu_key(key)
        elif key in MOVE_KEYS:
            self.held_direction = MOVE_KEYS[key]
            self._try_step(MOVE_KEYS[key])
        elif key in TALK_KEYS:
            if not self.is_moving:
                self._interact()
        elif key in MENU_KEYS:
            if not self.is_moving:
                self.mode = "MENU"

    def _handle_menu_key(self, key: int) -> None:
        if key in CANCEL_KEYS:
            self.mode = "WALK"
            return
        choice = self.pause_menu.handle_input(key)
        if choice is None:
            return
        self.mode = "WALK"
        if choice == 0:
            self.engine.push_scene(PokedexScene(self.engine))
        elif choice == 1:
            self.engine.push_scene(PartyScene(self.engine))
        elif choice == 2:
            self.engine.push_scene(BagScene(self.engine))
        elif choice == 3:
            self.engine.push_scene(CardScene(self.engine))
        elif choice == 4:
            self.show_notification("Game saved!" if self.save_game() else "Save failed!")
        # choice 5 (EXIT) just closes the menu

    # ------------------------------------------------------------------
    # Walking
    # ------------------------------------------------------------------
    def _try_step(self, direction: Direction) -> None:
        if self.is_moving or self.fade_dir != 0 or self.mode != "WALK":
            return
        before = self.explorer.location
        result: StepResult = self.explorer.step(direction)
        if result.blocked_lines:
            self._open_dialogue(result.blocked_lines)
            return
        if not result.moved:
            return
        if result.warped:
            # The model has already moved us; fade out, swap the map, fade back in.
            self.fade_dir, self.fade = 1, 0.0
            self._pending_map_change = before.map_id != self.explorer.location.map_id
            self.held_direction = None
            return
        self.step_from = (before.x, before.y)
        self.step_timer = 0.0

    def _finish_step(self) -> None:
        self.step_from = None
        self.walk_frame = 0
        table = self.explorer.roll_encounter(self.rng)
        if table:
            wild = self.engine.data_loader.get_wild_encounter(table)
            if wild:
                self.engine.game_state.pokedex.register_seen(wild.species_id)
                self.held_direction = None
                self._start_battle(BattleScene(self.engine, wild), WildTransition())
                return
        if self._check_spotted():
            return
        if self.held_direction and self.mode == "WALK":
            self._try_step(self.held_direction)

    # ------------------------------------------------------------------
    # Talking
    # ------------------------------------------------------------------
    def _open_dialogue(self, lines, then=None) -> None:
        """Show ``lines``; call ``then()`` when the player closes the last one."""
        self.held_direction = None
        self.dialogue = list(lines)
        self._after_dialogue = then
        self.mode = "DIALOGUE"
        self.textbox.set_message(self.dialogue.pop(0) if self.dialogue else "...")

    def _interact(self) -> None:
        state = self.engine.game_state
        result = self.explorer.interact(state)
        if result is None:
            return
        lines = list(result.lines)
        if result.effect == "healed":
            # Wake up here after blacking out.
            state.respawn_location = self.explorer.location
        elif result.effect == "give_items":
            for item_id, qty in result.data["items"].items():
                item = self.engine.data_loader.get_item(item_id, qty)
                state.trainer.add_item(item, qty)
                lines.append(f"{state.trainer.name} received {qty} {item.name}!")
        elif result.effect == "offer_starter":
            self._offer_starter(result.data["species_id"])
            return
        elif result.effect == "start_battle":
            trainer = result.data["trainer"]
            self._open_dialogue(lines, then=lambda: self._start_trainer_battle(trainer))
            return
        self._open_dialogue(lines)

    # ------------------------------------------------------------------
    # Trainers
    # ------------------------------------------------------------------
    def _check_spotted(self) -> bool:
        """After moving: if a trainer sees the player, freeze and show "!"."""
        spotter = self.explorer.spotted_by(self.engine.game_state)
        if spotter is None:
            return False
        self.spotter = spotter
        self.spotted_timer = self.SPOTTED_SECONDS
        self.held_direction = None
        self.mode = "SPOTTED"
        return True

    def _start_trainer_battle(self, trainer: TrainerNPC) -> None:
        loader, state = self.engine.data_loader, self.engine.game_state
        battle = trainer.build_battle(state, loader.get_type_chart(), loader.get_creature, loader.get_move)
        state.pokedex.register_seen(battle.opponent.species_id)
        self._start_battle(BattleScene(self.engine, battle.opponent, battle=battle), TrainerTransition())

    def _start_battle(self, battle_scene: BattleScene, transition: Transition) -> None:
        """Flash, wipe to black (the transition), then the battle; fade back in afterwards."""
        frame = self._last_frame if self._last_frame is not None else self.engine.native_surface
        self.fade, self.fade_dir = 1.0, -1   # when we're shown again, fade in from black
        self.engine.push_scene(TransitionScene(self.engine, frame, battle_scene, transition))

    def on_battle_end(self, battle) -> None:
        """Called by the battle scene when a battle the player didn't lose is over."""
        if battle.after_battle_lines:          # polymorphic: wild battles have none
            self._open_dialogue(battle.after_battle_lines)

    # ------------------------------------------------------------------
    # Choosing a starter
    # ------------------------------------------------------------------
    def _offer_starter(self, species_id: int) -> None:
        data = self.engine.data_loader.get_species_data(species_id)
        self.offered_species = species_id
        self.starter_menu.selected_index = 0
        self.held_direction = None
        self.mode = "CONFIRM_STARTER"
        self.textbox.set_message(f"Do you want {data['name'].upper()}, the {data['types'][0]} creature?")

    def _handle_starter_key(self, key: int) -> None:
        if not self.textbox.is_finished_typing:
            if key in ADVANCE_KEYS:
                self.textbox.advance()
            return
        choice = 1 if key in CANCEL_KEYS else self.starter_menu.handle_input(key)
        if choice is None:
            return
        species_id, self.offered_species = self.offered_species, None
        if choice == 1:
            self.mode = "WALK"
            return
        self._accept_starter(species_id)

    def _accept_starter(self, species_id: int) -> None:
        loader, state = self.engine.data_loader, self.engine.game_state
        starters = {e.species_id: loader.get_species_data(e.species_id)["types"]
                    for e in self.explorer.current_map.entities if isinstance(e, StarterBall)}
        rival = pick_rival_starter(species_id, starters, loader.get_type_chart())
        creature = loader.get_creature(species_id, level=5)
        give_starter(state, creature, rival)
        rival_name = loader.get_species_data(rival)["name"].upper()
        self._open_dialogue([
            f"{state.trainer.name} received {creature.name.upper()}!",
            f"{RIVAL_NAME}: Then I'll take {rival_name}! Its type is strong against yours.",
            f"{RIVAL_NAME}: Let's both get stronger. See you out there!",
        ])

    def _advance_dialogue(self) -> None:
        if not self.textbox.is_finished_typing:
            self.textbox.advance()
        elif self.dialogue:
            self.textbox.set_message(self.dialogue.pop(0))
        else:
            self.mode = "WALK"
            then, self._after_dialogue = self._after_dialogue, None
            if then:
                then()

    # ------------------------------------------------------------------
    # Update / draw
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.location_timer = max(0.0, self.location_timer - dt)
        if self.notification_timer > 0:
            self.notification_timer = max(0.0, self.notification_timer - dt)
            if self.notification_timer == 0:
                self.notification_text = None

        self.water_timer += dt
        if self.water_timer >= self.WATER_FRAME_SECONDS:
            self.water_timer = 0.0
            self.water_frame = (self.water_frame + 1) % 4

        self.textbox.update(dt)

        if self.mode == "SPOTTED":
            self.spotted_timer -= dt
            if self.spotted_timer <= 0:
                trainer, self.spotter = self.spotter, None
                trainer.turn_to(self._direction_from(trainer).opposite)
                challenge = trainer.challenge()
                self._open_dialogue(challenge.lines, then=lambda: self._start_trainer_battle(trainer))

        if self.fade_dir:
            self.fade += self.fade_dir * dt / self.FADE_SECONDS
            if self.fade_dir > 0 and self.fade >= 1.0:
                self.fade, self.fade_dir = 1.0, -1
                if self._pending_map_change:
                    self._pending_map_change = False
                    self._on_map_changed()
            elif self.fade_dir < 0 and self.fade <= 0.0:
                self.fade, self.fade_dir = 0.0, 0
                self._check_spotted()

        if self.step_from is not None:
            self.step_timer += dt
            progress = min(1.0, self.step_timer / self.STEP_SECONDS)
            self.walk_frame = (1, 0, 2, 0)[min(3, int(progress * 4))]
            if progress >= 1.0:
                self._finish_step()

    def _direction_from(self, entity) -> Direction:
        """Direction pointing from the player towards ``entity``."""
        loc = self.explorer.location
        dx, dy = entity.x - loc.x, entity.y - loc.y
        if abs(dx) >= abs(dy):
            return Direction.RIGHT if dx > 0 else Direction.LEFT
        return Direction.DOWN if dy > 0 else Direction.UP

    def _player_pixel_pos(self) -> Tuple[float, float]:
        loc = self.explorer.location
        if self.step_from is None:
            return float(loc.x * TILE), float(loc.y * TILE)
        t = min(1.0, self.step_timer / self.STEP_SECONDS)
        fx, fy = self.step_from
        return (fx + (loc.x - fx) * t) * TILE, (fy + (loc.y - fy) * t) * TILE

    def draw(self, surface: pygame.Surface) -> None:
        # While fading out of a map the model is already on the new one; keep
        # drawing the old map until the screen is black.
        if self._pending_map_change and self._last_frame is not None:
            surface.blit(self._last_frame, (0, 0))
            self._draw_fade(surface)
            return

        px, py = self._player_pixel_pos()
        cam = self.renderer.camera_offset(px, py)
        self.renderer.draw_ground(surface, cam, self.water_frame)

        # People, signs and the player, back to front
        world_map = self.explorer.current_map
        state = self.engine.game_state
        drawables = [(e.y, 0, e) for e in world_map.entities if e.is_present(state)]
        drawables.append((py / TILE, 1, None))
        for _, _, entity in sorted(drawables, key=lambda d: (d[0], d[1])):
            if entity is not None:
                self.renderer.draw_entity(surface, entity, cam)
            else:
                sprite = CharacterSprites.get("player", self.explorer.facing, self.walk_frame)
                surface.blit(sprite, (round(px) - cam[0], round(py) - cam[1] - (sprite.get_height() - TILE)))

        loc = self.explorer.location
        if world_map.tile_at(loc.x, loc.y).encounters:
            self.renderer.draw_grass_overlay(surface, px, py, cam)

        if self.mode == "SPOTTED" and self.spotter is not None:
            self._draw_exclamation(surface, self.spotter, cam)

        self._draw_hud(surface)
        if not self._pending_map_change:
            if self._last_frame is None or self._last_frame.get_size() != surface.get_size():
                self._last_frame = surface.copy()
            else:
                self._last_frame.blit(surface, (0, 0))
        self._draw_fade(surface)

    def _draw_fade(self, surface: pygame.Surface) -> None:
        if self.fade > 0:
            veil = pygame.Surface(surface.get_size())
            veil.set_alpha(int(255 * min(1.0, self.fade)))
            surface.blit(veil, (0, 0))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        if self.location_banner_visible:
            name = self.engine.game_state.current_route
            width = min(160, self.font.size(name)[0] + 16)
            slide = min(1.0, self.location_timer / 0.3)
            y = int(4 - (1.0 - slide) * 24)
            draw_gba_panel(surface, pygame.Rect(4, y, width, 18))
            draw_fitted_text(surface, name, 12, y + 1, width - 16, self.font)

        if self.notification_text and self.mode != "DIALOGUE":
            lines = wrap_text(self.notification_text, 216, self.font_sm)[:2]
            height = 8 + 13 * len(lines)
            box = pygame.Rect(4, 156 - height, 232, height)
            draw_gba_panel(surface, box)
            for i, line in enumerate(lines):
                draw_fitted_text(surface, line, box.x + 8, box.y + 4 + 13 * i, 216, self.font_sm)

        if self.mode == "DIALOGUE":
            self.textbox.draw(surface)
        elif self.mode == "CONFIRM_STARTER":
            self._draw_starter_preview(surface)
        elif self.mode == "MENU":
            self.pause_menu.draw(surface)

    def _draw_starter_preview(self, surface: pygame.Surface) -> None:
        sid = self.offered_species
        if sid is None:
            return
        data = self.engine.data_loader.get_species_data(sid)
        panel = pygame.Rect(76, 18, 88, 88)
        draw_gba_panel(surface, panel)
        sprite = SpriteRenderer.get_creature_sprite(sid, data["name"], data["types"][0],
                                                    is_back=False, size=(64, 64))
        surface.blit(sprite, (panel.x + 12, panel.y + 4))
        draw_fitted_text(surface, data["name"].upper(), panel.x + 4, panel.y + 70, panel.width - 8,
                         self.font_sm, align="center")
        self.textbox.draw(surface)
        if self.textbox.is_finished_typing:
            self.starter_menu.draw(surface)

    def _draw_exclamation(self, surface: pygame.Surface, entity, cam) -> None:
        x = entity.x * TILE - cam[0] + 3
        y = entity.y * TILE - cam[1] - 18
        bubble = pygame.Rect(x, y, 10, 12)
        pygame.draw.rect(surface, (248, 248, 248), bubble, border_radius=3)
        pygame.draw.rect(surface, (40, 40, 48), bubble, 1, border_radius=3)
        pygame.draw.rect(surface, (216, 48, 32), (x + 4, y + 2, 2, 5))
        pygame.draw.rect(surface, (216, 48, 32), (x + 4, y + 8, 2, 2))
