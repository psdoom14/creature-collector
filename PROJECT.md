# Project: Pokémon-Style Creature Collector Game Visual Overhaul

## Architecture
The application is a Pokémon-style creature collection and turn-based battle game built in Python with Pygame. It uses a strict Model-View-Controller architecture where:
- `src/model/` encapsulates pure game domain logic (Creature, Battle, Move, TypeChart, Trainer, Inventory, Item, SaveData) with **zero external UI or Pygame dependencies**.
- `src/ui/` contains Pygame presentation scenes (`OverworldScene`, `BattleScene`, `PartyScene`, `PokedexScene`), the rendering engine (`GameEngine`), reusable UI widgets (`components.py`), and the asset cache (`sprite_renderer.py`).
- Native screen resolution is 240×160 (exact Game Boy Advance resolution), scaled 3× to 720×480 in windowed mode.
- Overworld map is a 15×10 grid of 16×16 metatiles perfectly matching the 240×160 viewport.
- Data definitions live in `data/creatures.json` and `data/moves.json`.

```
                    ┌───────────────────────────────┐
                    │      src/model/ (Pure Logic)   │
                    │  Creature, Battle, Move, etc. │
                    └───────────────▲───────────────┘
                                    │ (read-only state & actions)
                    ┌───────────────┴───────────────┐
                    │       src/ui/ (Presentation)  │
┌───────────────────┼───────────────────────────────┼───────────────────┐
│ overworld_scene   │ battle_scene & components     │ sprite_renderer   │
│ - 16x16 GBA tiles │ - GBA battle pedestals        │ - 2-tier cache    │
│ - 4-dir walk anim │ - Notched HP boxes & EXP bars │ - 64x64 FRLG PNGs │
│ - Water animation │ - Crisp 1-bit pixel font      │ - Alpha channels  │
└───────────────────┴───────────────────────────────┴───────────────────┘
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | 25 Gen-3 Front Sprites | Authentic GBA FireRed/LeafGreen 64×64 front PNGs with alpha for all 25 species in `assets/sprites/` | M1 | Survey 1 |
| F2 | 25 Gen-3 Back Sprites | Authentic GBA FireRed/LeafGreen 64×64 back PNGs with alpha for all 25 species in `assets/sprites/` | M1 | Survey 1 |
| F3 | Two-Tier Sprite Renderer | Upgraded `src/ui/sprite_renderer.py` with 64×64 master cache + scaled cache, safe headless display handling, zero circle badges | M1 | Survey 1 |
| F4 | 16×16 GBA Overworld Tileset | Genuine 16×16 GBA tiles (`grass.png`, `tall_grass.png`, `tall_grass_overlay.png`, `path.png`, `tree.png`, 4-frame `water_*.png`, 3-tile PokéCenter façade) in `assets/tiles/` | M2 | Survey 2 |
| F5 | 4-Directional Trainer Sprites | 12-frame animated character walk cycle (Down, Up, Left, Right across Idle, Walk1, Walk2) in `assets/characters/trainer/` | M2 | Survey 2 |
| F6 | Upgraded Overworld Scene | `src/ui/overworld_scene.py` with TileManager, animated water (4 FPS), smooth step lerp, tall grass overlay, preserving collision and encounter mechanics | M2 | Survey 2 |
| F7 | GBA Battle Platforms | Tiered 3D pedestals (textured grass top, layered dirt bevel, drop shadow) in `src/ui/battle_scene.py` | M3 | Survey 3 |
| F8 | Classic GBA HP Boxes & HUD | Notched GBA card frames, HP badge icons, numeric HP, EXP bar, status pills (PSN, PAR, BRN, SLP, FRZ) in `src/ui/components.py` & `src/ui/battle_scene.py` | M3 | Survey 3 |
| F9 | Crisp Bitmap/Pixel Typography | Embedded pixel font or font loader with `antialias=False` and 1px drop shadow offset in `src/ui/components.py` | M3 | Survey 3 |
| F10 | Model-UI Architectural Isolation | Zero pygame imports in `src/model/`, all 14 existing unit tests continue to pass 100% | M4 | Survey 3 |
| F11 | Programmatic Asset Verification | Automated test suite validating all 50 sprite files (64×64, PNG, alpha), all 16×16 tiles, and character walk frames | M4 | Survey 1, 2 |
| F12 | Headless Scene Rendering Suite | Automated headless dry-run tests for OverworldScene, BattleScene, PartyScene, and PokedexScene using `SDL_VIDEODRIVER="dummy"` | M4 | Survey 3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Creature Sprites & Renderer | Ingest 50 Gen-3 FRLG sprites (F1, F2) into `assets/sprites/`; upgrade `src/ui/sprite_renderer.py` (F3) | none | DONE |
| M2 | Overworld Tileset & Character | Create/bundle 16×16 GBA tiles (F4) & trainer sprites (F5); overhaul `src/ui/overworld_scene.py` (F6) | none | DONE |
| M3 | Battle HUD, Pedestals & Typography | GBA battle platforms (F7), notched HP boxes & EXP bar (F8), crisp pixel font without blur (F9) | none | DONE |
| M4 | Final Integration & E2E Acceptance | Architectural check (F10), programmatic asset validation (F11), headless scene suite (F12), pass 100% E2E tests + audit | M1, M2, M3 | DONE |

## Interface Contracts

### 1. SpriteRenderer Contract (`src/ui/sprite_renderer.py`)
```python
class SpriteRenderer:
    @classmethod
    def get_creature_sprite(
        cls,
        name: str,
        size: tuple[int, int] = (64, 64),
        is_back: bool = False,
        creature_id: int | None = None
    ) -> pygame.Surface:
        """Returns a cached pygame.Surface with SRCALPHA. Never returns procedural circles when asset exists."""
        ...
```

### 2. Overworld Scene Contract (`src/ui/overworld_scene.py`)
- Grid size: 15 cols × 10 rows × 16 px = 240 × 160 px.
- Tile Types: 0=Path, 1=Grass, 2=Tree, 3=Water, 4=PokéCenter.
- Collision: `_can_move_to(tx, ty)` returns `tile not in (2, 3)` within bounds.
- Encounter: `current_tile == 1` triggers 20% random encounter on step completion.
- PokéCenter: `current_tile == 4` heals all party members.

### 3. Battle Scene & Component Contract (`src/ui/components.py`, `src/ui/battle_scene.py`)
- `draw_gba_hp_box(surface, rect, name, level, current_hp, max_hp, exp_ratio=None, status=None)`
- `draw_battle_platform(surface, center_x, center_y, width, height, is_player=False)`
- `draw_crisp_text(surface, text, x, y, font, color, shadow_color=None)`: Renders with `antialias=False` and optional 1px offset drop shadow.

## Code Layout
```
creature-collector/
├── assets/
│   ├── sprites/                  # 64x64 Gen-3 PNG sprites (bulbasaur_front.png, etc.)
│   ├── tiles/                    # 16x16 GBA pixel-art tiles (grass.png, path.png, etc.)
│   ├── characters/
│   │   └── trainer/              # 12 trainer walk cycle PNGs
│   └── fonts/                    # Crisp pixel font (or embedded bitmap table)
├── data/
│   ├── creatures.json            # 25 canonical Pokémon definitions
│   └── moves.json                # Move definitions
├── src/
│   ├── model/                    # Pure domain models (ZERO pygame imports!)
│   └── ui/
│       ├── engine.py             # 240x160 native surface, 3x scaling
│       ├── components.py         # GBA HP boxes, EXP bars, text renderer
│       ├── sprite_renderer.py    # Two-tier sprite caching
│       ├── overworld_scene.py    # TileManager, TrainerSpriteManager, 15x10 grid
│       ├── battle_scene.py       # Platforms, combatants, HP cards, menus
│       ├── party_scene.py        # Party UI
│       └── pokedex_scene.py      # Pokédex UI
└── tests/
    ├── test_battle.py            # Unit test
    ├── test_creature.py          # Unit test
    ├── test_save_load.py         # Unit test
    ├── test_type_chart.py        # Unit test
    ├── test_asset_verification.py # Automated asset validation (all 50 sprites & tiles)
    └── test_scene_rendering.py   # Headless scene rendering dry-run
```
