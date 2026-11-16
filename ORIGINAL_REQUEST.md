# Original User Request

## Initial Request — 2026-11-16T16:58:14Z

Comprehensive visual, sprite, tileset, and UI overhaul for the Pokémon-Style Creature Collector game to replace all placeholder geometric art with authentic GBA (FireRed/LeafGreen/Emerald) pixel-art assets and polished retro presentation.

Working directory: /home/psdoom14/.gemini/antigravity/scratch/creature-collector
Integrity mode: development

## Requirements

### R1. Authentic GBA Pokémon Sprites
Download or bundle authentic Gen-3 GBA (FireRed/LeafGreen/Emerald) pixel-art front and back sprites (64×64 PNG with transparent alpha) for all 23 creatures defined in data/creatures.json. Connect the sprite paths in data/creatures.json and src/ui/sprite_renderer.py.

### R2. GBA Overworld Tileset & Character Sprites
Replace all flat geometric tiles (rectangles and circles) in src/ui/overworld_scene.py with genuine 16×16 GBA pixel-art tiles for grass, paths, trees/forest borders, water edges, and the Pokémon Center building. Integrate a 4-directional animated character sprite for the trainer (walk cycles for Up, Down, Left, Right).

### R3. Authentic GBA Battle HUD & Typography
Overhaul src/ui/battle_scene.py and src/ui/components.py with authentic GBA battle platforms (grass/dirt pedestals beneath combatants), classic GBA HP boxes, and an embedded crisp bitmap/pixel font so text renders sharply without blur or scaling artifacts.

### R4. Architectural Preservation
Preserve the clean separation between src/model/ and src/ui/. Zero Pygame imports in src/model/. All 14 existing unit tests must continue to pass without modifications to core game rules.

## Verification Resources
- Test suite: python3 -m unittest discover tests -v (14 existing unit tests).
- Asset verification: Programmatic check that all 23 species have valid, non-placeholder PNG front and back sprites with transparency, and all overworld tiles exist and load.
- Scene rendering verification: Headless dry-run tests for OverworldScene, BattleScene, PartyScene, and PokedexScene.

## Acceptance Criteria

### Visual Assets & Rendering
- [ ] Every creature in data/creatures.json has an authentic GBA front and back sprite loaded from disk in assets/sprites/.
- [ ] No procedural geometric circles or placeholder letter badges ('C', 'R') appear during battles.
- [ ] Battle screen renders textured battle pedestals/platforms beneath the wild and player Pokémon.
- [ ] Battle HUD uses authentic GBA-style bordered HP boxes and status layouts.
- [ ] Overworld renders real 16×16 pixel-art tiles for path, grass, trees, water, and building.
- [ ] Player has a 4-direction animated pixel-art character sprite.
- [ ] In-game typography is crisp, readable, and free of bilinear blurring or distortion.

### Functionality & Tests
- [ ] python3 -m unittest discover tests -v executes with 100% passes (minimum 14 tests).
- [ ] Game runs from main.py without graphical crashes or missing asset exceptions.
- [ ] Wild encounters, battle animations, capturing, party view, and Pokédex browsing remain fully functional.
