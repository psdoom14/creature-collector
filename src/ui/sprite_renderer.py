"""Sprite loader, cache manager, and retro pixel-art renderer."""
import inspect
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
    """Manages creature sprite loading with two-tier caching and fallback."""

    _master_cache: Dict[str, pygame.Surface] = {}  # filename -> unscaled 64x64 master Surface
    _scaled_cache: Dict[str, pygame.Surface] = {}  # cache_key -> scaled Surface
    _cache: Dict[str, pygame.Surface] = _scaled_cache  # Backward-compatibility alias

    _ID_TO_NAME: Dict[int, str] = {}
    _NAME_TO_ID: Dict[str, int] = {}
    _NAME_TO_TYPE: Dict[str, str] = {}

    @classmethod
    def _init_creature_data(cls) -> None:
        if not cls._ID_TO_NAME and CREATURES_JSON.exists():
            try:
                with open(CREATURES_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for c in data:
                    cid = c["id"]
                    cname = c["name"]
                    cls._ID_TO_NAME[cid] = cname
                    cls._NAME_TO_ID[cname.lower()] = cid
                    if "types" in c and c["types"]:
                        cls._NAME_TO_TYPE[cname.lower()] = c["types"][0]
            except (OSError, ValueError, KeyError, TypeError) as e:
                logger.warning("Could not read creature data for sprites: %s", e)

    @classmethod
    def get_creature_sprite(
        cls,
        *args,
        **kwargs,
    ) -> pygame.Surface:
        """Returns a cached pygame.Surface with SRCALPHA. Never returns procedural circles when asset exists."""
        cls._init_creature_data()
        name, size, is_back, creature_id, primary_type = cls._resolve_args(*args, **kwargs)
        target_size = (int(size[0]), int(size[1]))

        # Cache key lookup in tier-2 cache
        cache_key = f"{name.lower()}_{'back' if is_back else 'front'}_{target_size[0]}x{target_size[1]}"
        if cache_key in cls._scaled_cache:
            return cls._scaled_cache[cache_key]

        # 1. Tier-1 Master surface lookup (unscaled 64x64)
        suffix = "back.png" if is_back else "front.png"
        filename = f"{name.lower()}_{suffix}"
        master_surf = cls._get_master_surface(filename)

        if master_surf is not None:
            # Nearest-neighbor scale to target size if different from native master
            if master_surf.get_size() == target_size:
                surf = master_surf
            else:
                surf = pygame.transform.scale(master_surf, target_size)
            cls._scaled_cache[cache_key] = surf
            if creature_id is not None:
                cls._scaled_cache[f"{creature_id}_{'back' if is_back else 'front'}_{target_size[0]}x{target_size[1]}"] = surf
            return surf

        # 2. Fallback procedural circle badge only if asset file is missing
        surf = cls._create_procedural_fallback(name, primary_type, is_back, target_size)
        cls._scaled_cache[cache_key] = surf
        if creature_id is not None:
            cls._scaled_cache[f"{creature_id}_{'back' if is_back else 'front'}_{target_size[0]}x{target_size[1]}"] = surf
        return surf

    @classmethod
    def _get_master_surface(cls, filename: str) -> Optional[pygame.Surface]:
        """Loads and returns unscaled 64x64 master surface with safe display initialization."""
        if filename in cls._master_cache:
            return cls._master_cache[filename]

        file_path = SPRITES_DIR / filename
        if file_path.exists():
            try:
                img = pygame.image.load(str(file_path))
                # Safely convert to video format only if display subsystem is initialized
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                cls._master_cache[filename] = img
                return img
            except (pygame.error, OSError) as e:
                logger.warning("Could not load sprite %s: %s", filename, e)
        return None

    @classmethod
    def _resolve_args(cls, *args, **kwargs) -> Tuple[str, Tuple[int, int], bool, Optional[int], str]:
        """Resolves (name, size, is_back, creature_id, primary_type) across both signatures."""
        name = ""
        size = (64, 64)
        is_back = False
        creature_id = None
        primary_type = "Normal"

        # Check kwargs
        if "name" in kwargs:
            name = str(kwargs["name"])
        if "size" in kwargs:
            size = kwargs["size"]
        if "is_back" in kwargs:
            is_back = bool(kwargs["is_back"])
        if "creature_id" in kwargs:
            creature_id = kwargs["creature_id"]
        if "species_id" in kwargs:
            creature_id = kwargs["species_id"]
        if "primary_type" in kwargs:
            primary_type = str(kwargs["primary_type"])

        # Check positional args
        if len(args) == 1:
            if isinstance(args[0], int):
                creature_id = args[0]
            else:
                name = str(args[0])
        elif len(args) >= 2:
            if isinstance(args[0], int):
                # Legacy positional: (species_id, name, [primary_type], [is_back], [size])
                creature_id = args[0]
                name = str(args[1])
                if len(args) >= 3:
                    primary_type = str(args[2])
                if len(args) >= 4:
                    is_back = bool(args[3])
                if len(args) >= 5:
                    size = args[4]
            else:
                # New positional: (name, [size], [is_back], [creature_id])
                name = str(args[0])
                if isinstance(args[1], (tuple, list)):
                    size = tuple(args[1])
                elif isinstance(args[1], str):
                    primary_type = args[1]
                if len(args) >= 3:
                    is_back = bool(args[2])
                if len(args) >= 4:
                    creature_id = args[3]

        # Harmonize name <-> creature_id
        if not name and creature_id is not None:
            name = cls._ID_TO_NAME.get(creature_id, "")
        elif name and creature_id is None:
            creature_id = cls._NAME_TO_ID.get(name.lower())

        if primary_type == "Normal" and name:
            primary_type = cls._NAME_TO_TYPE.get(name.lower(), "Normal")

        return name, size, is_back, creature_id, primary_type

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

    @classmethod
    def preload_all(cls) -> None:
        """Preloads all 50 creature master sprites into memory."""
        cls._init_creature_data()
        for cname in cls._NAME_TO_ID:
            cls._get_master_surface(f"{cname}_front.png")
            cls._get_master_surface(f"{cname}_back.png")


# Set inspectable method signature matching PROJECT.md interface contract
_SIG = inspect.Signature(
    parameters=[
        inspect.Parameter("cls", inspect.Parameter.POSITIONAL_ONLY),
        inspect.Parameter("name", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
        inspect.Parameter("size", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=(64, 64), annotation=Tuple[int, int]),
        inspect.Parameter("is_back", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=False, annotation=bool),
        inspect.Parameter("creature_id", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=Optional[int]),
    ],
    return_annotation=pygame.Surface,
)
SpriteRenderer.get_creature_sprite.__func__.__signature__ = _SIG

