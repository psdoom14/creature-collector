"""Drawing the overworld: tile art, character sprites, prerendered maps and the camera.

Tiles with a PNG in assets/tiles/ use it; every other tile is drawn in code here,
in the same 16x16 GBA style.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame

from src.model.direction import Direction
from src.model.entities import Character, Interactable, Sign, StarterBall
from src.model.world import WorldMap

TILE = 16
VIEW_W, VIEW_H = 240, 160
ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
WATER_FRAMES = 4

# --- palette ---------------------------------------------------------------
GRASS = (120, 192, 88)
GRASS_DARK = (88, 160, 72)
OUTLINE = (40, 40, 48)


def _shade(color: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, c + amount)) for c in color)


class TileArt:
    """16x16 tile images, loaded from assets or drawn in code, cached by name."""

    _cache: Dict[str, pygame.Surface] = {}

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    @classmethod
    def get(cls, name: str, water_frame: int = 0) -> pygame.Surface:
        key = f"water_{water_frame}" if name == "water" else name
        if key not in cls._cache:
            cls._cache[key] = cls._load(key) or cls._draw(key)
        return cls._cache[key]

    @classmethod
    def _load(cls, key: str) -> Optional[pygame.Surface]:
        path = ASSETS / "tiles" / f"{key}.png"
        if not path.exists():
            return None
        try:
            img = pygame.image.load(str(path))
            if pygame.display.get_surface() is not None:
                img = img.convert_alpha()
            return img if img.get_size() == (TILE, TILE) else pygame.transform.scale(img, (TILE, TILE))
        except pygame.error:
            return None

    @classmethod
    def _base_grass(cls) -> pygame.Surface:
        return cls.get("grass").copy()

    @classmethod
    def _draw(cls, key: str) -> pygame.Surface:
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        painter = getattr(cls, f"_paint_{key}", None)
        if painter:
            painter(s)
        elif key.startswith("water"):
            cls._paint_water(s, int(key[-1]) if key[-1].isdigit() else 0)
        else:
            s.fill((255, 0, 255))  # obviously wrong: unknown tile
        return s

    # --- outdoor -------------------------------------------------------
    @staticmethod
    def _paint_grass(s):
        s.fill(GRASS)
        for x, y in ((3, 4), (11, 2), (7, 11), (13, 13)):
            pygame.draw.line(s, GRASS_DARK, (x, y), (x + 1, y - 1))

    @staticmethod
    def _paint_path(s):
        s.fill((232, 216, 176))
        for x, y in ((4, 5), (11, 10), (2, 13)):
            s.set_at((x, y), (208, 188, 144))

    @staticmethod
    def _paint_tall_grass(s):
        TileArt._paint_grass(s)
        for x in (2, 6, 10, 14):
            pygame.draw.line(s, (56, 128, 48), (x, 15), (x, 6), 2)

    @staticmethod
    def _paint_tree(s):
        s.fill(GRASS)
        pygame.draw.rect(s, (112, 72, 40), (6, 10, 4, 6))
        pygame.draw.circle(s, (40, 104, 56), (8, 7), 7)
        pygame.draw.circle(s, (72, 144, 72), (6, 5), 3)

    @staticmethod
    def _paint_water(s, frame: int):
        s.fill((88, 152, 240))
        y = 4 + frame
        pygame.draw.line(s, (176, 216, 255), (2, y % 16), (7, y % 16))
        pygame.draw.line(s, (176, 216, 255), (9, (y + 7) % 16), (14, (y + 7) % 16))

    @classmethod
    def _paint_flowers(cls, s):
        s.blit(cls.get("grass"), (0, 0))
        for (x, y), col in zip(((4, 4), (11, 6), (6, 11), (12, 12)),
                               ((232, 72, 72), (248, 216, 64), (248, 248, 248), (232, 72, 72))):
            pygame.draw.circle(s, col, (x, y), 2)
            s.set_at((x, y), (248, 200, 64))

    @classmethod
    def _paint_fence(cls, s):
        s.blit(cls.get("grass"), (0, 0))
        for x in (2, 13):
            pygame.draw.rect(s, (248, 248, 240), (x, 3, 2, 12))
            pygame.draw.rect(s, OUTLINE, (x, 3, 2, 12), 1)
        for y in (5, 10):
            pygame.draw.rect(s, (248, 248, 240), (0, y, 16, 2))

    # --- buildings -----------------------------------------------------
    @staticmethod
    def _roof(s, base):
        s.fill(base)
        for y in (3, 8, 13):
            pygame.draw.line(s, _shade(base, -40), (0, y), (15, y))
        for y, off in ((0, 0), (5, 4), (10, 0)):
            for x in range(off, 16, 8):
                pygame.draw.line(s, _shade(base, -25), (x, y), (x, y + 2))

    @classmethod
    def _paint_house_roof(cls, s):
        cls._roof(s, (184, 88, 64))

    @staticmethod
    def _wall(s, base=(240, 224, 184)):
        s.fill(base)
        pygame.draw.line(s, _shade(base, -30), (0, 7), (15, 7))
        pygame.draw.line(s, _shade(base, -50), (0, 15), (15, 15))

    @classmethod
    def _paint_house_wall(cls, s):
        cls._wall(s)

    @classmethod
    def _paint_house_window(cls, s):
        cls._wall(s)
        pygame.draw.rect(s, (136, 192, 240), (3, 3, 10, 8))
        pygame.draw.rect(s, (88, 64, 48), (3, 3, 10, 8), 1)
        pygame.draw.line(s, (88, 64, 48), (8, 3), (8, 10))

    @classmethod
    def _paint_house_door(cls, s):
        cls._wall(s)
        pygame.draw.rect(s, (136, 80, 48), (3, 2, 10, 14))
        pygame.draw.rect(s, (80, 48, 32), (3, 2, 10, 14), 1)
        s.set_at((11, 9), (248, 216, 64))

    @classmethod
    def _paint_center_roof(cls, s):
        cls._roof(s, (224, 64, 56))

    @classmethod
    def _paint_center_sign(cls, s):
        cls._paint_center_roof(s)
        pygame.draw.rect(s, (248, 248, 248), (2, 2, 12, 12), border_radius=2)
        pygame.draw.rect(s, (224, 64, 56), (6, 4, 4, 8))
        pygame.draw.rect(s, (224, 64, 56), (4, 6, 8, 4))

    @classmethod
    def _paint_center_wall(cls, s):
        cls._wall(s, (240, 240, 232))
        pygame.draw.rect(s, (104, 168, 232), (1, 3, 14, 6))
        pygame.draw.line(s, (200, 232, 255), (2, 4), (13, 4))

    @classmethod
    def _paint_center_door(cls, s):
        cls._wall(s, (240, 240, 232))
        pygame.draw.rect(s, (160, 216, 248), (2, 2, 12, 14))
        pygame.draw.line(s, (96, 120, 144), (8, 2), (8, 15))
        pygame.draw.rect(s, (96, 120, 144), (2, 2, 12, 14), 1)

    @classmethod
    def _paint_gym_roof(cls, s):
        cls._roof(s, (72, 144, 136))

    @classmethod
    def _paint_gym_wall(cls, s):
        s.fill((176, 176, 184))
        for y in (4, 9, 14):
            pygame.draw.line(s, (136, 136, 152), (0, y), (15, y))
        for x, y in ((4, 0), (12, 5), (6, 10)):
            pygame.draw.line(s, (136, 136, 152), (x, y), (x, y + 3))

    @classmethod
    def _paint_gym_door(cls, s):
        cls._paint_gym_wall(s)
        pygame.draw.rect(s, (56, 64, 88), (3, 3, 10, 13))
        pygame.draw.rect(s, (248, 208, 64), (3, 3, 10, 2))

    # --- indoors ---------------------------------------------------------
    @staticmethod
    def _paint_floor(s):
        s.fill((232, 224, 208))
        pygame.draw.rect(s, (216, 204, 184), (0, 0, 8, 8))
        pygame.draw.rect(s, (216, 204, 184), (8, 8, 8, 8))

    @staticmethod
    def _paint_wall(s):
        s.fill((216, 200, 168))
        pygame.draw.rect(s, (168, 144, 112), (0, 12, 16, 4))
        pygame.draw.line(s, (240, 232, 208), (0, 2), (15, 2))

    @classmethod
    def _paint_mat(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (200, 64, 56), (1, 2, 14, 12))
        pygame.draw.rect(s, (152, 40, 40), (1, 2, 14, 12), 1)

    @classmethod
    def _paint_counter(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (176, 112, 64), (0, 2, 16, 12))
        pygame.draw.rect(s, (216, 160, 104), (0, 2, 16, 4))
        pygame.draw.line(s, (112, 72, 40), (0, 13), (15, 13))

    @classmethod
    def _paint_machine(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (176, 184, 200), (1, 2, 14, 13), border_radius=2)
        for x, y in ((5, 6), (10, 6), (5, 11), (10, 11)):
            pygame.draw.circle(s, (224, 64, 56), (x, y), 2)

    @classmethod
    def _paint_plant(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (168, 96, 56), (4, 10, 8, 5))
        pygame.draw.circle(s, (64, 152, 72), (8, 7), 5)
        pygame.draw.circle(s, (104, 192, 96), (6, 5), 2)

    @classmethod
    def _paint_table(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (200, 168, 120), (0, 3, 16, 10))
        pygame.draw.line(s, (232, 208, 160), (0, 4), (15, 4))
        pygame.draw.line(s, (136, 104, 64), (0, 12), (15, 12))

    @classmethod
    def _paint_bookshelf(cls, s):
        s.fill((136, 88, 48))
        for y, cols in ((2, ((224, 72, 72), (72, 120, 200), (88, 168, 88))),
                        (9, ((232, 200, 72), (160, 96, 184), (224, 72, 72)))):
            for i, col in enumerate(cols):
                pygame.draw.rect(s, col, (2 + i * 4, y, 3, 5))
        pygame.draw.line(s, (88, 56, 32), (0, 8), (15, 8))

    @classmethod
    def _paint_pc(cls, s):
        cls._paint_floor(s)
        pygame.draw.rect(s, (200, 204, 216), (2, 2, 12, 9))
        pygame.draw.rect(s, (72, 136, 200), (4, 4, 8, 5))
        pygame.draw.rect(s, (152, 156, 168), (5, 11, 6, 4))


class CharacterSprites:
    """Player frames from assets; NPCs are colour-swapped copies of them."""

    PALETTES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = {
        # name: (cap/shirt colour, trousers colour)
        "player": ((216, 44, 40), (56, 96, 168)),
        "green": ((64, 168, 88), (88, 72, 56)),
        "blue": ((56, 112, 200), (64, 64, 80)),
        "brown": ((152, 104, 64), (80, 88, 96)),
        "purple": ((144, 88, 184), (56, 64, 104)),
        "orange": ((232, 136, 48), (72, 88, 136)),
        "pink": ((240, 144, 176), (248, 248, 248)),
    }
    _cache: Dict[Tuple[str, str, int], pygame.Surface] = {}

    @classmethod
    def get(cls, palette: str, facing: Direction, frame: int = 0) -> pygame.Surface:
        key = (palette, facing.key, frame % 3)
        if key not in cls._cache:
            base = cls._player_frame(facing, frame % 3)
            cls._cache[key] = base if palette == "player" else cls._recolor(base, palette)
        return cls._cache[key]

    @classmethod
    def _player_frame(cls, facing: Direction, frame: int) -> pygame.Surface:
        name = ("idle", "walk1", "walk2")[frame]
        path = ASSETS / "characters" / "trainer" / f"trainer_{facing.key}_{name}.png"
        try:
            img = pygame.image.load(str(path))
            return img.convert_alpha() if pygame.display.get_surface() is not None else img
        except (pygame.error, FileNotFoundError):
            surf = pygame.Surface((16, 20), pygame.SRCALPHA)
            pygame.draw.circle(surf, (216, 44, 40), (8, 5), 5)
            pygame.draw.rect(surf, (56, 96, 168), (4, 9, 8, 9))
            return surf

    @classmethod
    def _recolor(cls, base: pygame.Surface, palette: str) -> pygame.Surface:
        top, bottom = cls.PALETTES.get(palette, cls.PALETTES["green"])
        out = base.copy()
        w, h = out.get_size()
        for x in range(w):
            for y in range(h):
                r, g, b, a = out.get_at((x, y))
                if a == 0:
                    continue
                if r > 130 and g < 100 and b < 100:            # reds: cap and jacket
                    lum = r / 216
                    out.set_at((x, y), (*(min(255, int(c * lum)) for c in top), a))
                elif b > 100 and r < 80:                         # blues: trousers
                    lum = b / 168
                    out.set_at((x, y), (*(min(255, int(c * lum)) for c in bottom), a))
        return out


def ball_sprite() -> pygame.Surface:
    """A small red-and-white catch ball resting on a table."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    pygame.draw.circle(s, (248, 248, 248), (8, 8), 5)
    pygame.draw.rect(s, (224, 56, 48), (3, 3, 11, 5))
    pygame.draw.circle(s, (40, 40, 48), (8, 8), 5, 1)
    pygame.draw.line(s, (40, 40, 48), (3, 8), (13, 8))
    pygame.draw.circle(s, (248, 248, 248), (8, 8), 2)
    pygame.draw.circle(s, (40, 40, 48), (8, 8), 2, 1)
    return s


def sign_sprite() -> pygame.Surface:
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    pygame.draw.rect(s, (112, 72, 40), (7, 9, 2, 7))
    pygame.draw.rect(s, (200, 152, 96), (2, 2, 12, 8), border_radius=1)
    pygame.draw.rect(s, (112, 72, 40), (2, 2, 12, 8), 1)
    for y in (4, 7):
        pygame.draw.line(s, (136, 96, 56), (4, y), (11, y))
    return s


class MapRenderer:
    """Prerenders a map's tiles once (one image per water frame) and draws it through a camera."""

    def __init__(self, world_map: WorldMap):
        self.map = world_map
        self.pixel_w = world_map.width * TILE
        self.pixel_h = world_map.height * TILE
        self._frames: List[pygame.Surface] = [self._render(f) for f in range(WATER_FRAMES)]
        self._sign = sign_sprite()
        self._ball = ball_sprite()

    def _render(self, water_frame: int) -> pygame.Surface:
        surf = pygame.Surface((self.pixel_w, self.pixel_h))
        for y in range(self.map.height):
            for x in range(self.map.width):
                name = self.map.tile_name(x, y)
                tile = TileArt.get(name, water_frame)
                if name in ("tall_grass", "flowers", "fence", "tree"):
                    surf.blit(TileArt.get("grass"), (x * TILE, y * TILE))
                surf.blit(tile, (x * TILE, y * TILE))
        return surf

    def camera_offset(self, focus_px: float, focus_py: float) -> Tuple[int, int]:
        """Top-left of the view in map pixels, centred on the focus and clamped to the map."""
        def axis(focus, size, view):
            if size <= view:
                return -(view - size) // 2  # small map: centre it
            return int(max(0, min(size - view, focus - view // 2)))
        return axis(focus_px + 8, self.pixel_w, VIEW_W), axis(focus_py + 8, self.pixel_h, VIEW_H)

    def draw_ground(self, surface: pygame.Surface, cam: Tuple[int, int], water_frame: int) -> None:
        surface.fill((0, 0, 0))
        surface.blit(self._frames[water_frame % WATER_FRAMES], (-cam[0], -cam[1]))

    def draw_entity(self, surface: pygame.Surface, entity: Interactable, cam: Tuple[int, int]) -> None:
        sx, sy = entity.x * TILE - cam[0], entity.y * TILE - cam[1]
        if isinstance(entity, Character):
            sprite = CharacterSprites.get(entity.palette, entity.facing)
            surface.blit(sprite, (sx, sy - (sprite.get_height() - TILE)))
        elif isinstance(entity, Sign):
            surface.blit(self._sign, (sx, sy))
        elif isinstance(entity, StarterBall):
            surface.blit(self._ball, (sx, sy - 3))

    def draw_grass_overlay(self, surface: pygame.Surface, px: float, py: float, cam: Tuple[int, int]) -> None:
        """Tall-grass blades over the lower half of whoever stands in it."""
        sx, sy = round(px) - cam[0], round(py) - cam[1]
        for x in (2, 6, 10, 14):
            pygame.draw.line(surface, (56, 128, 48), (sx + x, sy + 15), (sx + x, sy + 9), 2)
