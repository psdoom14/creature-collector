# 📜 Project Handover Document — Pokémon-Style Creature Collector (GBA)

> **Prepared For**: Claude Opus 5.5 / Successor AI Agent  
> **Date**: November 17, 2026  
> **Project Working Directory**: `/home/psdoom14/.gemini/antigravity/scratch/creature-collector`  
> **GitHub Repository**: [https://github.com/psdoom14/creature-collector](https://github.com/psdoom14/creature-collector) (Private, user: `psdoom14`)  
> **Primary Stack**: Python 3.11+ / Pygame 2.6.1 / JSON Data Store  
> **Current Test Status**: 37 / 37 automated tests passing in `< 0.5s`

---

## 1. Executive Summary & Context

This project is an **Object-Oriented Programming (OOP) Showcase** implementing a Pokémon-style turn-based creature collector game with **Game Boy Advance (Gen-3 FireRed/Emerald)** aesthetics.

The project was initially created as a terminal and Pygame prototype, then received a major visual overhaul replacing all geometric placeholder art with authentic 64×64 Gen-3 creature sprites, 16×16 overworld tiles, and a custom GBA battle HUD.

**Current State**:
- Core combat, XP, leveling, evolution, catching, items, type effectiveness, and JSON save/load systems are **fully working and tested**.
- Visual assets for 25 species (50 sprites), tiles, and fonts are **integrated and verified**.
- **Critical Gaps Remaining**: The world design is currently confined to a single 15×10 screen. The Pokémon Center is an un-enterable facade on the top boundary wall. The Party and Pokédex screens have text-clipping layout bugs.

---

## 2. Sacred Architectural Rules (DO NOT BREAK)

1. **Zero Pygame Imports in `src/model/` (Strict MVC / Clean Architecture)**:
   - All game logic, formulas, entities, and battle mechanics live in `src/model/`.
   - **Under no circumstances should `pygame` or any visual library be imported in `src/model/`**.
   - Verification check: `grep -rn "pygame" src/model/` MUST always return `0`.
2. **Event-Driven UI**:
   - `Battle` does not render or print anything. It yields immutable `BattleEvent` dataclasses. The UI (`src/ui/battle_scene.py`) reads these events and drives animations and textboxes.
3. **Data-Driven Rules**:
   - Pokémon stats, moves, type effectiveness, items, and encounter rates live in `data/*.json`. Never hardcode species stats or move damage into code.
4. **Resolution & Scaling**:
   - Native rendering is strictly **240×160 pixels** (GBA resolution).
   - Pygame scales the native surface 3× to a **720×480 window** (`GameEngine.SCALE = 3`).
   - All UI coordinates and tile math must be designed in 240×160 space.

---

## 3. Project Directory Map

```
creature-collector/
├── main.py                     # Primary launcher (graphical Pygame or --cli fallback)
├── terminal_demo.py            # Headless text prototype with ASCII HP bars
├── requirements.txt            # Dependencies (pygame>=2.5.0)
├── HANDOVER.md                 # This handover document
├── README.md                   # Comprehensive user-facing documentation
├── .gitignore                  # Git ignore rules (pycache, savegame.json, etc.)
│
├── data/                       # JSON Game Databases
│   ├── creatures.json          # 25 species stats, learnsets, evolutions, sprites
│   ├── moves.json              # 40 physical, special, and status moves
│   ├── items.json              # Poké Balls, Potions, Revives, Status cures
│   ├── type_chart.json         # 15×15 type effectiveness multiplier matrix
│   └── encounters.json         # Route-based encounter tables & level ranges
│
├── assets/                     # Game Assets
│   ├── sprites/                # 50 Gen-3 64×64 PNGs (front & back for 25 species)
│   ├── tiles/                  # 12 16×16 PNG tiles (grass, path, trees, water_0..3, pokecenter)
│   ├── characters/trainer/     # 12 16×20 PNG trainer frames (4 directions × 3 walk states)
│   └── fonts/                  # TrueType pixel fonts (PressStart2P, Silkscreen, pokemon-font)
│
├── src/
│   ├── model/                  # DOMAIN MODEL (ZERO Pygame imports)
│   │   ├── creature.py         # Creature base + FireCreature, WaterCreature, etc.
│   │   ├── move.py             # Move base + AttackMove, StatusMove + MoveFactory
│   │   ├── item.py             # Item base + HealingItem, CatchBall, ReviveItem, StatusCureItem
│   │   ├── battle.py           # Battle engine, BattleState enum, BattleEvent stream
│   │   ├── trainer.py          # Trainer & Party (max 6, active lead tracking)
│   │   ├── pokedex.py          # Pokedex tracking (seen & caught sets)
│   │   ├── type_chart.py       # TypeChart calculation & effectiveness messages
│   │   └── game_state.py       # GameState snapshot & serialization
│   │
│   ├── ui/                     # PRESENTATION LAYER
│   │   ├── engine.py           # GameEngine (scaler, scene stack, 60 FPS clock)
│   │   ├── scene.py            # Abstract Scene base class
│   │   ├── components.py       # HPBar, EXPBar, TextBox, MenuBox, draw_gba_panel, crisp fonts
│   │   ├── sprite_renderer.py  # 2-tier sprite cache (unscaled + scaled)
│   │   ├── battle_scene.py     # 3D tiered pedestals, notched HP cards, duel engine
│   │   ├── overworld_scene.py  # Tilemap exploration, wild grass triggers, walk cycles
│   │   ├── party_scene.py      # Party health & lineup viewer
│   │   └── pokedex_scene.py    # Scrollable Pokédex browser
│   │
│   ├── data_loader.py          # Repository & factory loading data/*.json into model objects
│   └── save_manager.py         # JSON disk persistence for GameState
│
├── scripts/
│   └── capture_stages.py       # Headless screenshot generation utility
│
├── screenshots/                # Automated gameplay stage captures (stage1 .. stage6)
└── tests/                      # Automated Test Suite (37 tests)
    ├── test_type_chart.py      # Type multiplier tests
    ├── test_creature.py        # Stat calculations, XP, evolution triggers
    ├── test_battle.py          # Combat turn execution, catch, and flee formulas
    ├── test_save_load.py       # Save/load roundtrip verification
    ├── test_asset_verification.py       # 50 sprites, 12 tiles, 12 frames validation
    ├── test_battle_hud_and_components.py # HUD notches, EXP bar, drop shadow fonts
    └── test_scene_rendering.py          # Headless scene lifecycle dry-runs
```

---

## 4. Empirical Flaws & Forensic Audit Findings

The automated test runner captures screenshots of gameplay stages into `screenshots/`. Forensic review revealed four critical issues:

### 🔴 Flaw 1: The "Fake" Pokémon Center (`stage2_overworld_pokecenter.png`)
- **Current Behavior**: The Pokémon Center is literally 3 tiles (`pokecenter_left`, `pokecenter_center`, `pokecenter_right`) placed on the top boundary wall (`row 0`).
- Walking into it does **not** open a door or enter an interior.
- The player sprite is drawn standing on top of the building's roof/glass.
- Stepping on it calls `party.heal_all()` and displays a cut-off notification banner: `Healing Center: Party re...`.
- **Target Fix**: Implement an authentic enterable Pokémon Center building with a front door warp that transitions to an interior scene (`PokeCenterInteriorScene`) featuring tiled floors, a service counter, and Nurse Joy with interactive dialogue.

### 🔴 Flaw 2: Single-Screen Claustrophobic World (`stage1_overworld.png`)
- **Current Behavior**: The entire game world is a single static 15×10 tilemap surrounded completely by solid trees.
- There are no exits, no Route 1 vs Pallet Town vs Viridian City, and nowhere to explore.
- **Target Fix**: Implement an interconnected multi-area map engine:
  - **Pallet Town** (Starting town with houses, lab, fences, and a north exit)
  - **Route 1** (Winding road with tall grass encounter zones, ledges, and trees)
  - **Viridian City** (Streets, Pokémon Center building, Poké Mart)
  - Edge/boundary warps between maps.

### 🔴 Flaw 3: Party Screen Text Collision (`stage5_party.png`)
- **Current Behavior**: In `src/ui/party_scene.py`, the horizontal layout positions are hardcoded. For a 10-character Pokémon name like `CHARMANDER`, the name collides directly into the `Lv.5` text and the HP bar, producing an unreadable overlap: `CHARMANDERLv.5[HP] 18/18`.
- **Target Fix**: Re-architect `PartyScene` with strict column bounding boxes:
  - Column 1: Icon (x=24, w=16)
  - Column 2: Name (x=44, w=60)
  - Column 3: Level (x=108, w=30)
  - Column 4: HP Bar (x=142, w=45)
  - Column 5: Numeric HP (x=192, w=36)

### 🔴 Flaw 4: Pokédex Screen Truncation (`stage6_pokedex.png`)
- **Current Behavior**: In `src/ui/pokedex_scene.py`:
  - Header: `POKÉDEX  CAUGHT: 1  SEEN:` truncates the number.
  - Left column list: `#004 CHARMAND` truncates the trailing `ER`.
  - Footer prompt: `ESC/X to retu` truncates the trailing `rn`.
- **Target Fix**: Widen the left list card from 140px to 148px, reduce entry text margins, and format header text to fit comfortably within the 232px width.

---

## 5. Next Implementation Tasks for Claude Opus 5.5

Here is the exact prioritized roadmap ready for immediate execution:

### Task 1: Multi-Map World Engine
1. In `src/ui/overworld_scene.py` (or a new `src/ui/world_manager.py`), define maps as data or modular classes:
   - `MAP_PALLET_TOWN` (e.g. 15×12 or 20×15)
   - `MAP_ROUTE_1` (e.g. 15×25 vertical scroll, or multi-screen)
   - `MAP_VIRIDIAN_CITY` (e.g. 20×15)
2. Implement **Warp / Edge Triggers**:
   - Walking past the northern edge of Pallet Town loads Route 1 with the player placed at the southern edge.
   - Walking past the northern edge of Route 1 loads Viridian City.
   - Walking into the Pokémon Center door loads the interior.
3. Update `game_state.current_route` dynamically based on the active map.

### Task 2: Enterable Pokémon Center with Nurse Joy
1. Create `src/ui/pokecenter_scene.py` (or sub-map interior):
   - Interior dimensions: 15×10 (fits native GBA screen perfectly).
   - Visual layout: Red-patterned floor tiles, back wall, service counter with Nurse Joy sprite, healing machine with 6 Poké Ball slots, and PC terminal on the right.
2. Interaction Logic:
   - Approaching the counter and pressing `Z` or `Enter` faces Nurse Joy.
   - Dialogue triggers via `TextBox`:
     - *"Hello, and welcome to the Pokémon Center!"*
     - *"We restore your tired Pokémon to full health."*
     - *"Would you like to heal your party?"*
   - Flashes/beeps the healing machine, calls `player.party.heal_all()`.
   - *"Thank you! Your Pokémon are fully rested. We hope to see you again!"*
3. Stepping onto the bottom door mat transitions back to the city directly in front of the center.

### Task 3: Fix UI Text Collisions
1. Edit `src/ui/party_scene.py`: Fix slot layout coordinates so long names (`CHARMANDER`, `BLASTOISE`) have plenty of room before the level and HP bars.
2. Edit `src/ui/pokedex_scene.py`: Fix card widths and font sizes so no strings are clipped.

### Task 4: Interactive NPCs & Signposts
1. Add an entity layer to maps:
   - `NPC`: `(x, y, sprite, dialogue_lines, direction)`
   - `Signpost`: `(x, y, message)`
2. When player presses `Z`/`Enter`, check the tile directly ahead of `player_facing`. If an NPC or sign is there, trigger a `TextBox` with their dialogue!

---

## 6. Verification & CLI Commands

Always run these commands to verify your changes:

```bash
cd /home/psdoom14/.gemini/antigravity/scratch/creature-collector

# 1. Run all 37 tests (must pass 100%)
python3 -m unittest discover tests -v

# 2. Check architecture isolation (MUST return 0)
grep -rn "pygame" src/model/ | wc -l

# 3. Generate fresh screenshots of all play stages
python3 -c "
import os, sys
sys.path.insert(0, '.')
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['LC_ALL'] = 'C.UTF-8'
import pygame
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.battle_scene import BattleScene
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene

os.makedirs('screenshots', exist_ok=True)
engine = GameEngine()

# Capture overworld
ow = OverworldScene(engine)
engine.push_scene(ow)
ow.update(0.1)
ow.draw(engine.native_surface)
pygame.image.save(pygame.transform.scale(engine.native_surface, (720, 480)), 'screenshots/stage1_overworld.png')

# Capture battle
wild = engine.data_loader.get_creature(25, 5)
bs = BattleScene(engine, wild)
engine.push_scene(bs)
bs.update(0.1)
bs.draw(engine.native_surface)
pygame.image.save(pygame.transform.scale(engine.native_surface, (720, 480)), 'screenshots/stage3_battle_encounter.png')
print('Screenshots updated successfully!')
"

# 4. Launch game interactively
python3 main.py

# 5. Git status & commit
git status
git add .
git commit -m "Your commit message"
git push origin main
```

---

## 7. Known Environment Quirks
- **Python Version**: Python 3.14.9 on Linux (x86_64).
- **Pygame Font Fix**: `pygame.font` under Python 3.14 has a circular import with `sysfont`. This has been fixed in `~/.local/lib/python3.14/site-packages/pygame/font.py`, and `src/ui/components.py` has a multi-tier fallback mechanism.
- **Headless Running**: When running scripts in background or subagent mode, always set `os.environ["SDL_VIDEODRIVER"] = "dummy"` and `os.environ["LC_ALL"] = "C.UTF-8"` before importing Pygame.
