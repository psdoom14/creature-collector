# Test Infrastructure & Methodology: Creature Collector

## 1. Overview & Architecture
The testing infrastructure for Creature Collector is designed to provide comprehensive, automated validation across both the pure domain model and the graphical presentation layer. It ensures retro visual authenticity, zero regressions in core battle/capture mechanics, and strict architectural decoupling between domain logic and Pygame rendering.

### Decoupled Architecture Validation
- **Pure Model Tier (`src/model/`)**: Deterministic game logic containing zero dependencies on Pygame, OS windowing, or audio systems. Verifiable via fast headless unit tests.
- **Presentation Tier (`src/ui/`)**: Pygame rendering scenes (`OverworldScene`, `BattleScene`, `PartyScene`, `PokedexScene`), two-tier sprite caching (`SpriteRenderer`), and UI components (`components.py`).
- **Asset Integrity Tier (`assets/`)**: Authentic Gen-3 Game Boy Advance (FireRed / LeafGreen / Emerald) assets including 64x64 creature sprites, 16x16 metatiles, and 4-directional animated trainer walk cycle frames.

### Headless Display Harness
Pygame scenes and sprite renderers are fully tested without physical displays or X11/Wayland servers by configuring:
```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
```
This enables dry-run execution of scene initialization, tick updates, event handling, and surface rendering inside CI/CD pipelines and headless development environments.

---

## 2. Test Execution & Runner Guide

The test suite uses Python's standard `unittest` framework, requiring no external third-party test runners.

### Running the Entire Suite
```bash
python3 -m unittest discover tests -v
```

### Running Specific Test Modules
- **Unit & Model Tests**:
  ```bash
  python3 -m unittest tests/test_creature.py -v
  python3 -m unittest tests/test_battle.py -v
  python3 -m unittest tests/test_type_chart.py -v
  python3 -m unittest tests/test_save_load.py -v
  ```
- **Asset Integrity & Specification Verification**:
  ```bash
  python3 -m unittest tests/test_asset_verification.py -v
  ```
- **Headless UI & Scene Rendering**:
  ```bash
  python3 -m unittest tests/test_scene_rendering.py -v
  ```

---

## 3. The 4-Tier Testing Methodology

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 4: Real-World Scenarios & E2E Verification              │
│ - 50 GBA 64x64 PNG sprites (RGBA alpha, dimensions)        │
│ - 16x16 GBA Overworld tiles & 12 trainer walk cycle frames  │
│ - Headless scene lifecycle (Overworld, Battle, Party, Dex)  │
│ - Strict Model-UI isolation (0 pygame imports in model/)    │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: Cross-Feature Interactions                          │
│ - Battle victory triggers XP gain, level-up & evolution     │
│ - Successful capture registers species in Pokédex & Party   │
│ - Overworld PokéCenter heals entire trainer party           │
│ - Save/Load state roundtrip preserving full inventory/party │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Boundary & Corner Cases                             │
│ - Dual-type quad weakness (4x) and complete immunity (0x)   │
│ - Stat floor and faint boundaries (0 HP)                    │
│ - Full party handling and empty bag selections              │
│ - Route boundaries and impassable tiles (water/trees)       │
├─────────────────────────────────────────────────────────────┤
│ Tier 1: Unit & Feature Coverage                             │
│ - Base stats initialization, move learnsets, damage formulas│
│ - Turn orders, player move execution, run/flee mechanics    │
│ - Item effects (healing, revive, catch rates)               │
│ - Sprite cache hits and surface generation                  │
└─────────────────────────────────────────────────────────────┘
```

### Tier 1: Unit & Feature Coverage
Focuses on individual class behaviors, methods, and deterministic logic:
- `Creature`: Base stat calculations, current vs. max HP, move slot allocation (up to 4 moves), XP accumulation.
- `Battle`: Turn execution, damage calculation incorporating STAB (Same-Type Attack Bonus) and stats.
- `Move`: Category classification (Physical vs. Special vs. Status), power, accuracy, PP deduction.
- `TypeChart`: Single-type attack vs. defense effectiveness lookups.
- `Trainer` & `Inventory`: Item management, quantity counting, party ordering.

### Tier 2: Boundary & Corner Cases
Stresses edge conditions and mathematical boundary limits:
- **Type Effectiveness Boundaries**:
  - Dual typing resulting in 4x super-effective multipliers (e.g. Electric vs Gyarados Water/Flying).
  - Dual typing resulting in 0.25x resistances.
  - Complete immunities returning 0.0x multiplier (e.g. Normal vs Ghost, Ground vs Flying).
- **HP & State Transitions**:
  - Overkill damage clamping precisely at 0 HP (no negative HP).
  - Healing capped strictly at `max_hp`.
  - Revive items strictly rejected on conscious creatures, functioning only on fainted creatures.
- **Overworld Navigation**:
  - Collision boundaries rejecting movement into trees (Tile 2) and water (Tile 3).
  - Boundary bounds checks preventing movement beyond 15x10 metatiles.

### Tier 3: Cross-Feature Interactions
Validates interconnected systems across multiple modules:
- **Level-Up & Evolution**: Battle victory grants XP; when crossing `xp_to_next_level`, level increments, stats recalculate, and evolution conditions (`into` species ID) trigger.
- **Catch & Pokédex Registration**: Using a Poké Ball in battle calculates catch probability based on current HP ratio, status, and species catch rate; upon success, the creature is added to the Trainer's party/storage and marked as caught in the `Pokedex`.
- **Healing Stations**: Overworld step onto PokéCenter tile (Tile 4) triggers party-wide heal restoring all creature HP and resetting status ailments.
- **Serialization Roundtrip**: `SaveManager` dumps complete `GameState` (Trainer name, money, inventory, party members with IVs/EVs/moves, Pokédex seen/caught sets) to JSON and reloads an exact functional replica.

### Tier 4: Real-World Scenarios & E2E Acceptance
Validates visual assets, UI rendering pipelines, and architectural rules:
- **Asset Integrity Verification (`test_asset_verification.py`)**:
  - Every one of the 25 canonical species in `data/creatures.json` must have both front (`<name.lower()>_front.png`) and back (`<name.lower()>_back.png`) sprites.
  - All 50 creature sprite files must be valid PNGs, exactly 64x64 pixels, with transparent alpha channels (`RGBA` or `LA`).
  - All 16x16 GBA overworld metatiles exist in `assets/tiles/`: `grass.png`, `tall_grass.png`, `tall_grass_overlay.png`, `path.png`, `tree.png`, 4 animated `water_*.png`, and 3 PokéCenter façade tiles (`pokecenter_left.png`, `pokecenter_center.png`, `pokecenter_right.png`).
  - All 12 trainer walk cycle frames exist in `assets/characters/trainer/` across 4 directions (down, up, left, right) and 3 states (idle, walk1, walk2).
- **Headless Scene Rendering (`test_scene_rendering.py`)**:
  - Initializing `OverworldScene`, `BattleScene`, `PartyScene`, and `PokedexScene` on a 240x160 native surface without display errors.
  - Running update cycles (`update(dt=0.016)`) and rendering cycles (`draw(surface)`).
  - Verifying `SpriteRenderer.get_creature_sprite()` returns genuine Pygame surfaces without fallback circles or exceptions.
- **Architectural Boundary Enforcement**:
  - Static AST/regex inspection asserting zero `import pygame` occurrences across all `src/model/*.py` modules.

---

## 4. Quality Status & Coverage Metrics

| Test Module | Primary Target | Tier | Target Tests |
|---|---|:---:|:---:|
| `tests/test_creature.py` | Stat growth, HP capping, level-up & evolution | Tier 1 & 2 | 4 |
| `tests/test_battle.py` | Turn mechanics, damage, XP, catch, flee | Tier 1 & 3 | 4 |
| `tests/test_type_chart.py` | Neutral, effective, resistance, quad, immunity | Tier 1 & 2 | 5 |
| `tests/test_save_load.py` | Full state serialization and deserialization | Tier 3 | 1 |
| `tests/test_asset_verification.py` | 50 sprites (64x64 RGBA), 16x16 tiles, 12 trainer frames | Tier 4 | 7 |
| `tests/test_scene_rendering.py` | Headless scene lifecycle, SpriteRenderer, Model isolation | Tier 4 | 6 |
| **Total** | **Full Project Acceptance** | **All** | **27 tests** |

All tests must execute cleanly with 100% pass rate in headless environments.
