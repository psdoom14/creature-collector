"""Overworld scene with authentic GBA tile-based exploration, animated water, smooth movement, and walk cycles."""
import pygame
import random
from pathlib import Path
from typing import Optional, Dict, Tuple

from src.ui.scene import Scene
from src.ui.battle_scene import BattleScene
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene
from src.ui.components import draw_gba_panel, MenuBox, TextBox, get_font, COLOR_TEXT_DARK
from src.save_manager import SaveManager


class TileManager:
    """Loads and caches 16x16 GBA overworld tiles with procedural fallbacks."""
    _tiles: Dict[str, pygame.Surface] = {}

    @classmethod
    def clear_cache(cls) -> None:
        cls._tiles.clear()

    @classmethod
    def get_tile(cls, tile_name: str) -> pygame.Surface:
        if tile_name in cls._tiles:
            return cls._tiles[tile_name]

        # Resolve asset path
        tile_path = Path(__file__).resolve().parent.parent.parent / "assets" / "tiles" / f"{tile_name}.png"
        if tile_path.exists():
            try:
                img = pygame.image.load(str(tile_path))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                if img.get_size() != (16, 16):
                    img = pygame.transform.scale(img, (16, 16))
                cls._tiles[tile_name] = img
                return img
            except Exception:
                pass

        # Procedural fallback
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        cls._render_fallback(surf, tile_name)
        cls._tiles[tile_name] = surf
        return surf

    @classmethod
    def _render_fallback(cls, surf: pygame.Surface, tile_name: str) -> None:
        t_rect = pygame.Rect(0, 0, 16, 16)
        if "grass" in tile_name:
            if tile_name == "tall_grass_overlay":
                # Transparent overlay with two small blade lines
                pygame.draw.line(surf, (72, 144, 48), (4, 15), (4, 10), 2)
                pygame.draw.line(surf, (72, 144, 48), (11, 15), (11, 11), 2)
            else:
                pygame.draw.rect(surf, (120, 192, 88), t_rect)
                if tile_name == "tall_grass":
                    pygame.draw.line(surf, (72, 144, 48), (4, 12), (4, 4), 2)
                    pygame.draw.line(surf, (72, 144, 48), (11, 12), (11, 5), 2)
        elif "path" in tile_name:
            pygame.draw.rect(surf, (232, 216, 176), t_rect)
        elif "tree" in tile_name:
            pygame.draw.rect(surf, (48, 104, 56), t_rect)
            pygame.draw.circle(surf, (32, 80, 40), (8, 7), 6)
        elif "water" in tile_name:
            pygame.draw.rect(surf, (88, 152, 240), t_rect)
            pygame.draw.line(surf, (168, 208, 255), (3, 7), (12, 7), 1)
        elif "pokecenter" in tile_name:
            pygame.draw.rect(surf, (224, 72, 72), t_rect)
            pygame.draw.line(surf, (255, 255, 255), (8, 3), (8, 13), 2)
            pygame.draw.line(surf, (255, 255, 255), (3, 8), (13, 8), 2)
        else:
            pygame.draw.rect(surf, (128, 128, 128), t_rect)


class TrainerSpriteManager:
    """Loads and caches 4-directional trainer walk cycle frames (idle, walk1, walk2)."""
    _sprites: Dict[Tuple[str, int], pygame.Surface] = {}

    @classmethod
    def clear_cache(cls) -> None:
        cls._sprites.clear()

    @classmethod
    def get_sprite(cls, facing: str, frame_idx: int) -> pygame.Surface:
        key = (facing, frame_idx % 3)
        if key in cls._sprites:
            return cls._sprites[key]

        frame_name = ["idle", "walk1", "walk2"][frame_idx % 3]
        sprite_path = (
            Path(__file__).resolve().parent.parent.parent
            / "assets"
            / "characters"
            / "trainer"
            / f"trainer_{facing}_{frame_name}.png"
        )

        if sprite_path.exists():
            try:
                img = pygame.image.load(str(sprite_path))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                cls._sprites[key] = img
                return img
            except Exception:
                pass

        # If right direction asset missing, attempt mirror flip from left
        if facing == "right":
            left_sprite = cls.get_sprite("left", frame_idx)
            flipped = pygame.transform.flip(left_sprite, True, False)
            cls._sprites[key] = flipped
            return flipped

        # Procedural fallback sprite
        surf = pygame.Surface((16, 20), pygame.SRCALPHA)
        # Cap
        pygame.draw.circle(surf, (200, 48, 48), (8, 5), 5)
        # Jacket
        pygame.draw.rect(surf, (40, 72, 160), pygame.Rect(4, 8, 8, 7))
        # Direction indicator
        fx, fy = 8, 6
        if facing == "up":
            fy -= 2
        elif facing == "down":
            fy += 2
        elif facing == "left":
            fx -= 2
        elif facing == "right":
            fx += 2
        pygame.draw.circle(surf, (248, 224, 192), (fx, fy), 2)
        cls._sprites[key] = surf
        return surf


class OverworldScene(Scene):
    """Grid-based exploration screen matching GBA Pallet Town / Route 1 aesthetics."""

    TILE_SIZE = 16
    GRID_W = 15
    GRID_H = 10

    # Tile Types: 0=Path, 1=Grass, 2=Tree, 3=Water, 4=PokeCenter
    MAP_DATA = [
        [2, 2, 2, 2, 2, 4, 4, 4, 2, 2, 2, 2, 2, 2, 2],
        [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2],
        [2, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2],
        [2, 0, 1, 1, 0, 2, 2, 0, 0, 0, 1, 1, 1, 1, 2],
        [2, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2],
        [2, 1, 1, 1, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 2],
        [2, 1, 1, 1, 0, 0, 0, 0, 3, 3, 3, 0, 1, 1, 2],
        [2, 1, 1, 1, 0, 0, 0, 0, 3, 3, 3, 0, 1, 1, 2],
        [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2],
        [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    ]

    def __init__(self, engine):
        super().__init__(engine)
        self.player_x = 7
        self.player_y = 4
        self.player_facing = "down"  # up, down, left, right

        # Smooth grid walking state
        self.is_moving: bool = False
        self.move_timer: float = 0.0
        self.move_duration: float = 0.20  # 200ms per step lerp
        self.start_tile_x: int = self.player_x
        self.start_tile_y: int = self.player_y
        self.target_tile_x: int = self.player_x
        self.target_tile_y: int = self.player_y
        self.walk_frame: int = 0  # 0=idle, 1=walk1, 2=walk2

        # Animated water state
        self.water_timer: float = 0.0
        self.water_frame: int = 0
        self.water_frame_duration: float = 0.25  # 4 FPS (250ms per frame)

        self.font = get_font(10)
        self.font_sm = get_font(9)

        # In-game pause menu
        self.is_menu_open = False
        self.pause_menu = MenuBox(
            pygame.Rect(150, 8, 84, 88),
            ["POKÉDEX", "POKÉMON", "BAG", "SAVE", "EXIT"],
            columns=1,
        )

        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0

    def show_notification(self, text: str, duration: float = 2.0) -> None:
        self.notification_text = text
        self.notification_timer = duration

    def _can_move_to(self, tx: int, ty: int) -> bool:
        if not (0 <= tx < self.GRID_W and 0 <= ty < self.GRID_H):
            return False
        tile = self.MAP_DATA[ty][tx]
        # Cannot walk on trees (2) or water (3)
        return tile not in (2, 3)

    def _try_move(self, dx: int, dy: int) -> None:
        if self.is_moving:
            return

        nx = self.player_x + dx
        ny = self.player_y + dy

        if dx > 0:
            self.player_facing = "right"
        elif dx < 0:
            self.player_facing = "left"
        elif dy > 0:
            self.player_facing = "down"
        elif dy < 0:
            self.player_facing = "up"

        if self._can_move_to(nx, ny):
            self.is_moving = True
            self.move_timer = 0.0
            self.start_tile_x = self.player_x
            self.start_tile_y = self.player_y
            self.target_tile_x = nx
            self.target_tile_y = ny

    def _on_step(self) -> None:
        current_tile = self.MAP_DATA[self.player_y][self.player_x]

        # Tall grass step -> encounter chance (1 in 5 steps)
        if current_tile == 1:
            if random.random() < 0.20:
                wild = self.engine.data_loader.get_wild_encounter(self.engine.game_state.current_route)
                if wild:
                    self.engine.game_state.pokedex.register_seen(wild.species_id)
                    self.engine.push_scene(BattleScene(self.engine, wild))
                    return

        # Pokémon Center step -> full heal!
        elif current_tile == 4:
            self.engine.game_state.trainer.party.heal_all()
            self.show_notification("Healing Center: Party restored!")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        key = event.key

        if self.is_menu_open:
            if key in (pygame.K_ESCAPE, pygame.K_x):
                self.is_menu_open = False
            else:
                choice = self.pause_menu.handle_input(key)
                if choice is not None:
                    if choice == 0:  # POKEDEX
                        self.is_menu_open = False
                        self.engine.push_scene(PokedexScene(self.engine))
                    elif choice == 1:  # POKEMON
                        self.is_menu_open = False
                        self.engine.push_scene(PartyScene(self.engine))
                    elif choice == 2:  # BAG
                        self.is_menu_open = False
                        bag_items = [f"{it.name} x{it.quantity}" for it in self.engine.game_state.trainer.inventory.values()]
                        self.show_notification(", ".join(bag_items) or "Bag empty", 3.0)
                    elif choice == 3:  # SAVE
                        SaveManager.save_game(self.engine.game_state, "savegame.json")
                        self.is_menu_open = False
                        self.show_notification("Game saved to savegame.json!")
                    elif choice == 4:  # EXIT
                        self.is_menu_open = False
            return

        # Normal Overworld movement (ignore if currently executing a step)
        if self.is_moving:
            return

        if key in (pygame.K_UP, pygame.K_w):
            self._try_move(0, -1)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._try_move(0, 1)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._try_move(-1, 0)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._try_move(1, 0)
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            self.is_menu_open = True

    def update(self, dt: float) -> None:
        if self.notification_timer > 0:
            self.notification_timer = max(0.0, self.notification_timer - dt)
            if self.notification_timer == 0.0:
                self.notification_text = None

        # Water animation cycle (4 FPS)
        self.water_timer += dt
        if self.water_timer >= self.water_frame_duration:
            self.water_timer = 0.0
            self.water_frame = (self.water_frame + 1) % 4

        # Smooth grid walking interpolation and walk cycle
        if self.is_moving:
            self.move_timer += dt
            alpha = min(1.0, self.move_timer / self.move_duration)

            # 4-stage walk cycle: idle -> walk1 -> idle -> walk2
            if alpha < 0.25:
                self.walk_frame = 1
            elif alpha < 0.50:
                self.walk_frame = 0
            elif alpha < 0.75:
                self.walk_frame = 2
            else:
                self.walk_frame = 0

            if self.move_timer >= self.move_duration:
                self.player_x = self.target_tile_x
                self.player_y = self.target_tile_y
                self.is_moving = False
                self.walk_frame = 0
                self._on_step()

    def draw(self, surface: pygame.Surface) -> None:
        # 1. Render Tiles
        for r in range(self.GRID_H):
            for c in range(self.GRID_W):
                tile = self.MAP_DATA[r][c]
                rx = c * self.TILE_SIZE
                ry = r * self.TILE_SIZE

                if tile == 0:  # Path
                    surface.blit(TileManager.get_tile("path"), (rx, ry))
                elif tile == 1:  # Tall Grass
                    surface.blit(TileManager.get_tile("grass"), (rx, ry))
                    surface.blit(TileManager.get_tile("tall_grass"), (rx, ry))
                elif tile == 2:  # Tree
                    surface.blit(TileManager.get_tile("tree"), (rx, ry))
                elif tile == 3:  # Water (animated 4-frame)
                    surface.blit(TileManager.get_tile(f"water_{self.water_frame}"), (rx, ry))
                elif tile == 4:  # PokeCenter Modular Façade
                    if c == 5:
                        surface.blit(TileManager.get_tile("pokecenter_left"), (rx, ry))
                    elif c == 6:
                        surface.blit(TileManager.get_tile("pokecenter_center"), (rx, ry))
                    elif c == 7:
                        surface.blit(TileManager.get_tile("pokecenter_right"), (rx, ry))
                    else:
                        surface.blit(TileManager.get_tile("pokecenter_center"), (rx, ry))

        # 2. Render Player with smooth position interpolation
        if self.is_moving:
            alpha = min(1.0, self.move_timer / self.move_duration)
            px = (self.start_tile_x + (self.target_tile_x - self.start_tile_x) * alpha) * self.TILE_SIZE
            py = (self.start_tile_y + (self.target_tile_y - self.start_tile_y) * alpha) * self.TILE_SIZE
        else:
            px = float(self.player_x * self.TILE_SIZE)
            py = float(self.player_y * self.TILE_SIZE)

        player_sprite = TrainerSpriteManager.get_sprite(self.player_facing, self.walk_frame)
        sprite_offset_y = player_sprite.get_height() - self.TILE_SIZE
        surface.blit(player_sprite, (round(px), round(py - sprite_offset_y)))

        # 3. Tall grass foot immersion overlay
        center_tile_x = int((px + 8) // self.TILE_SIZE)
        center_tile_y = int((py + 8) // self.TILE_SIZE)
        is_in_tall_grass = False
        if 0 <= center_tile_x < self.GRID_W and 0 <= center_tile_y < self.GRID_H:
            if self.MAP_DATA[center_tile_y][center_tile_x] == 1:
                is_in_tall_grass = True
        if not is_in_tall_grass and self.MAP_DATA[self.player_y][self.player_x] == 1:
            is_in_tall_grass = True

        if is_in_tall_grass:
            surface.blit(TileManager.get_tile("tall_grass_overlay"), (round(px), round(py)))

        # 4. Route HUD header
        draw_gba_panel(surface, pygame.Rect(4, 4, 80, 16))
        route_lbl = self.font_sm.render(self.engine.game_state.current_route, True, COLOR_TEXT_DARK)
        surface.blit(route_lbl, (8, 6))

        # 5. Notification Banner
        if self.notification_text:
            draw_gba_panel(surface, pygame.Rect(10, 136, 220, 20))
            notif = self.font_sm.render(self.notification_text, True, (180, 40, 30))
            surface.blit(notif, (16, 140))

        # 6. Pause Menu
        if self.is_menu_open:
            self.pause_menu.draw(surface)
