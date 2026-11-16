# 🎮 Pokémon-Style Creature Collector (GBA)

A complete, retro **Pokémon-style turn-based creature collector** built in **Python and Pygame** using pure **Object-Oriented Programming (OOP)** principles and authentic **Game Boy Advance (Gen-3)** visual aesthetics.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Pygame](https://img.shields.io/badge/Pygame-2.6%2B-green?logo=pygame)
![OOP Architecture](https://img.shields.io/badge/Architecture-Clean%20OOP%20%2F%20MVC-orange)
![Tests](https://img.shields.io/badge/Tests-37%2F37%20Passing-brightgreen)

---

## 🌟 Highlights

- **Pure OOP Domain Layer**: The game rules, damage formulas, creatures, moves, items, and battle logic live in `src/model/` with **zero UI dependencies** (0 Pygame imports in model).
- **Authentic GBA Aesthetics**: Native **240×160 resolution** scaled 3× to a crisp 720×480 window with 1-bit pixel drop-shadow typography, 3D tiered battle pedestals, and notched GBA HP boxes.
- **50 Authentic Gen-3 Sprites**: 64×64 pixel-art front and back battle sprites for 25 species.
- **16×16 Overworld Tileset**: Animated water, textured grass, tree borders, and a Pokémon Center healing building.
- **4-Direction Animated Trainer**: Smooth 0.20s step walk cycle with tall-grass foot immersion.
- **Comprehensive Test Suite**: 37 automated tests covering unit domain logic, sprite asset integrity, and headless visual rendering.

---

## 🏛️ OOP Concepts & Design Patterns

| OOP Concept | Implementation in Code |
|---|---|
| **Abstraction** | Abstract base classes (`Move`, `Item`, `Scene`) define unified contracts via `@abstractmethod`. |
| **Inheritance** | `AttackMove` and `StatusMove` extend `Move`; `FireCreature`, `WaterCreature`, and `ElectricCreature` extend `Creature`; `HealingItem` and `CatchBall` extend `Item`. |
| **Polymorphism** | `item.use(target)` and `item.can_use(target)` dynamically behave differently for every item subclass; type-specific creatures override passive status immunities (e.g. Fire cannot be burned, Electric cannot be paralyzed). |
| **Encapsulation** | Health points, experience, and stat stages are protected and can only be altered through domain methods (`take_damage()`, `heal()`, `gain_xp()`, `revive()`). |
| **Composition** | `Trainer` *has-a* `Party` *which has-a* list of `Creature`s *which have-a* list of `Move`s. |
| **State Machine** | `BattleState` enum (`SELECTING_ACTION`, `SELECTING_MOVE`, `SELECTING_ITEM`, `WON`, `LOST`, `CAUGHT`, `FLED`) governs the turn lifecycle. |
| **Event-Driven UI** | The `Battle` engine yields a stream of immutable `BattleEvent` objects that the UI layer translates into animations and dialogs. |
| **Factory Pattern** | `CreatureFactory`, `MoveFactory`, and `ItemFactory` parse raw JSON dictionaries into concrete subclass instances. |
| **Persistence (Serialization)** | `GameState.to_dict()` and `GameState.from_dict()` handle full save/load state to disk via `SaveManager`. |

---

## 🕹️ How to Play

### 1. Requirements & Setup
```bash
# Clone the repository
git clone https://github.com/psdoom14/creature-collector.git
cd creature-collector

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch the Game
```bash
# Graphical Mode (Pygame GBA UI)
python3 main.py

# Terminal / CLI Mode (Text-only with colored ASCII HP bars)
python3 terminal_demo.py
# or:
python3 main.py --cli
```

### Controls
| Key | Action |
|---|---|
| **Arrow Keys / W, A, S, D** | Move trainer in Overworld / Navigate menus |
| **Enter / Space / Z** | Confirm selection / Advance dialogue |
| **Esc / X / Backspace** | Cancel / Back / Open Pause Menu |
| **F11** | Toggle Fullscreen |

---

## 📁 Project Structure

```
creature-collector/
├── main.py                     # Game launcher (GBA graphics or CLI fallback)
├── terminal_demo.py            # Playable text-based prototype
├── requirements.txt            # Python dependencies (pygame)
├── data/                       # Game configuration & tables (JSON)
│   ├── creatures.json          # 25 species stats, learnsets, evolutions
│   ├── moves.json              # 40 physical, special, and status moves
│   ├── items.json              # Poké Balls, Potions, Revives, Status cures
│   ├── type_chart.json         # Full Gen-1 type effectiveness matrix
│   └── encounters.json         # Route-based wild encounter tables
├── assets/                     # Pixel art & font assets
│   ├── sprites/                # 50 Gen-3 64×64 front and back battle sprites
│   ├── tiles/                  # 12 16×16 GBA overworld tiles
│   ├── characters/             # 12 trainer walk-cycle frames
│   └── fonts/                  # TrueType retro pixel fonts
├── src/
│   ├── model/                  # PURE DOMAIN MODEL (Zero Pygame dependencies)
│   │   ├── creature.py         # Creature base & type subclasses
│   │   ├── move.py             # Move hierarchy & MoveFactory
│   │   ├── item.py             # Item hierarchy (Potions, CatchBalls, Revives)
│   │   ├── battle.py           # Battle engine & BattleEvent stream
│   │   ├── trainer.py          # Trainer & Party composition
│   │   ├── pokedex.py          # Pokédex tracking
│   │   ├── type_chart.py       # Damage multiplier calculations
│   │   └── game_state.py       # Game state snapshot
│   ├── ui/                     # PRESENTATION LAYER
│   │   ├── engine.py           # Window scaler & scene stack manager
│   │   ├── scene.py            # Abstract Scene base
│   │   ├── components.py       # Notched GBA HP boxes, crisp text, menus
│   │   ├── sprite_renderer.py  # Sprite caching & asset pipeline
│   │   ├── battle_scene.py     # 3D battle platforms & duel screen
│   │   ├── overworld_scene.py  # Tile map, animated trainer, encounters
│   │   ├── party_scene.py      # Party health viewer
│   │   └── pokedex_scene.py    # Scrollable Pokédex browser
│   ├── data_loader.py          # Central data repository & factory
│   └── save_manager.py         # JSON disk persistence
└── tests/                      # 37 automated tests
    ├── test_type_chart.py      # Type calculation & effectiveness tests
    ├── test_creature.py        # Stats, leveling, evolution tests
    ├── test_battle.py          # Combat turn loop, catch, run tests
    ├── test_save_load.py       # Save/load roundtrip tests
    ├── test_asset_verification.py # Sprite dimensions & alpha validation
    ├── test_battle_hud_and_components.py # Notched HP box & font tests
    └── test_scene_rendering.py # Headless scene lifecycle dry-runs
```

---

## 🧪 Running Tests

Execute the full 37-test suite:
```bash
python3 -m unittest discover tests -v
```

All 37 tests execute in `< 0.5s` and verify:
- Unit domain mechanics (damage formulas, XP curves, evolutions, catching)
- Asset integrity (all 50 creature sprites, 12 tiles, and 12 character frames have valid dimensions and alpha channels)
- HUD & typography components (1-bit font crispness, notched HP boxes, 3D pedestals)
- Headless rendering of all scenes without exceptions
- Architecture isolation (`grep -rn "pygame" src/model/` returns 0)

---

## 📄 License
MIT License. Created for educational and personal portfolio purposes.
