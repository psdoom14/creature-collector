"""Creature sprite loading and caching."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame
from src.ui.components import TYPE_COLORS

SPRITES_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "sprites"
CREATURES_JSON = Path(__file__).resolve().parent.parent.parent / "data" / "creatures.json"

logger = logging.getLogger(__name__)


class SpriteRenderer:
    """Loads creature sprites (front and back) with a two-level cache.

    Level 1 keeps each PNG as loaded; level 2 keeps it scaled to each size asked for.
    If a sprite file is missing, a simple drawn badge in the creature's type colour
    is used instead, so the game never crashes on a missing image.
    """

    _master_cache: Dict[str, pygame.Surface] = {}   # file name -> image as loaded
    _scaled_cache: Dict[Tuple, pygame.Surface] = {}  # (species, back?, size) -> scaled image
    _names: Dict[int, str] = {}
    _types: Dict[int, str] = {}

    @classmethod
    def _load_species(cls) -> None:
        if cls._names or not CREATURES_JSON.exists():
            return
        try:
            with open(CREATURES_JSON, "r", encoding="utf-8") as f:
                for c in json.load(f):
                    cls._names[c["id"]] = c["name"]
                    cls._types[c["id"]] = (c.get("types") or ["Normal"])[0]
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning("Could not read creature data for sprites: %s", e)

    @classmethod
    def get_creature_sprite(cls, species_id: int, name: str = "", primary_type: str = "",
                            is_back: bool = False, size: Tuple[int, int] = (64, 64)) -> pygame.Surface:
        """The sprite for ``species_id`` (front or back) at ``size``; name and type are looked
        up from the species when not given."""
        cls._load_species()
        name = name or cls._names.get(species_id, "")
        primary_type = primary_type or cls._types.get(species_id, "Normal")
        target_size = (int(size[0]), int(size[1]))
        key = (species_id, name.lower(), is_back, target_size)
        if key in cls._scaled_cache:
            return cls._scaled_cache[key]

        master = cls._get_master_surface(f"{name.lower()}_{'back' if is_back else 'front'}.png")
        if master is None:
            surf = cls._create_procedural_fallback(name, primary_type, is_back, target_size)
        elif master.get_size() == target_size:
            surf = master
        else:
            surf = pygame.transform.scale(master, target_size)   # nearest-neighbour keeps pixels crisp
        cls._scaled_cache[key] = surf
        return surf

    @classmethod
    def _get_master_surface(cls, filename: str) -> Optional[pygame.Surface]:
        """The image as loaded from assets/sprites/, or None if it is missing."""
        if filename in cls._master_cache:
            return cls._master_cache[filename]
        file_path = SPRITES_DIR / filename
        if file_path.exists():
            try:
                img = pygame.image.load(str(file_path))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                cls._master_cache[filename] = img
                return img
            except (pygame.error, OSError) as e:
                logger.warning("Could not load sprite %s: %s", filename, e)
        return None

    @classmethod
    def _create_procedural_fallback(cls, name: str, primary_type: str, is_back: bool, size: Tuple[int, int]) -> pygame.Surface:
        """Procedural badge fallback only when sprite image is missing from disk."""
        surf = pygame.Surface(size, pygame.SRCALPHA)
        main_color = TYPE_COLORS.get(primary_type.capitalize(), (160, 160, 160))
        dark_color = (max(0, main_color[0] - 60), max(0, main_color[1] - 60), max(0, main_color[2] - 60))
        highlight = (min(255, main_color[0] + 50), min(255, main_color[1] + 50), min(255, main_color[2] + 50))

        w, h = size
        cx, cy = w // 2, h // 2

        if not is_back:
            pygame.draw.circle(surf, dark_color, (cx, cy + 4), 18)
            pygame.draw.circle(surf, main_color, (cx, cy + 4), 16)
            pygame.draw.circle(surf, dark_color, (cx, cy - 8), 13)
            pygame.draw.circle(surf, highlight, (cx, cy - 8), 11)
            pygame.draw.circle(surf, (30, 30, 40), (cx - 4, cy - 8), 2)
            pygame.draw.circle(surf, (30, 30, 40), (cx + 4, cy - 8), 2)
            pygame.draw.circle(surf, (255, 255, 255), (cx - 5, cy - 9), 1)
            pygame.draw.circle(surf, (255, 255, 255), (cx + 3, cy - 9), 1)
        else:
            pygame.draw.circle(surf, dark_color, (cx, cy + 2), 22)
            pygame.draw.circle(surf, main_color, (cx, cy + 2), 20)
            pygame.draw.circle(surf, dark_color, (cx, cy - 10), 15)
            pygame.draw.circle(surf, highlight, (cx, cy - 10), 13)

        if name:
            font = pygame.font.SysFont("monospace", 10, bold=True)
            lbl = font.render(name[0], True, (255, 255, 255))
            lbl_rect = lbl.get_rect(center=(cx, cy + (6 if not is_back else 4)))
            surf.blit(lbl, lbl_rect)

        return surf

    @classmethod
    def clear_cache(cls) -> None:
        """Clears both tier-1 master cache and tier-2 scaled cache."""
        cls._master_cache.clear()
        cls._scaled_cache.clear()
