# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Multi-map world expansion, enterable buildings, and UI fixes
> Requested team: Full Team

Transform the creature collector world from a single isolated 15×10 clearing into a multi-area interconnected game world with Pallet Town, Route 1, and Viridian City, complete with enterable Pokémon Center interior, Nurse Joy healing dialogue, interactive NPCs, and complete UI clipping fixes across Party and Pokédex screens.

Working directory: `/home/psdoom14/.gemini/antigravity/scratch/creature-collector`
Integrity mode: development

## Requirements

### R1. Multi-Area Interconnected World System
Implement a flexible multi-map world system supporting seamless map transitions:
1. **Pallet Town**: Starting town with houses, flower beds, fences, and a north exit to Route 1.
2. **Route 1**: Winding country road with tall grass encounter zones, ledges, signposts, and north exit to Viridian City.
3. **Viridian City**: Bustling city with roads, buildings, and an enterable Pokémon Center.
Transition occurs when the player steps on defined border transition tiles or exits.

### R2. Enterable Pokémon Center & Nurse Joy Healing
Replace the top-wall roof tile with an authentic enterable Pokémon Center:
- Walking into the Pokémon Center door triggers a screen transition to the **Pokémon Center Interior** scene/map.
- Includes the service counter, PC terminal, and Nurse Joy sprite.
- Pressing `Z`/`Enter` when facing Nurse Joy triggers classic dialogue: *"Welcome to our Pokémon Center! We heal your Pokémon back to perfect health."* -> heals party -> *"Your Pokémon are fighting fit! We hope to see you again!"*.
- Stepping on the bottom mat/door transitions back to the outside city in front of the center.

### R3. UI Clipping & Layout Overhaul
Fix all text collisions and truncation identified in screenshots:
- **Party Scene**: Fix horizontal layout so 10+ character names (`CHARMANDER`), level tags (`Lv.5`), and HP bars have dedicated column zones and never collide.
- **Pokédex Scene**: Expand entry card width and header/footer margins so species names (`#004 CHARMANDER`), header counters (`POKÉDEX  CAUGHT: 1  SEEN: 2`), and instructions (`▲▼ Scroll | ESC/X Return`) never truncate.
- **Location HUD**: Make the route/town banner semi-transparent or position it cleanly so it never obscures buildings.

### R4. NPC Dialogue & Signposts
- Add interactive NPCs in towns with speech bubbles / bottom dialogue boxes when pressing `Z`/`Enter`.
- Signposts that display location names or helpful tips when inspected.

### R5. Architecture & Test Preservation
- Preserve clean separation: `src/model/` has zero Pygame imports.
- Maintain and expand automated test coverage (all 37 existing tests must pass, plus new tests for map transitions and indoor scenes).

## Verification Resources
- Test suite: `python3 -m unittest discover tests -v` (37 existing tests + new map/indoor tests).
- Automated screenshot verification: `scripts/capture_stages.py` verifying all 3 maps, indoor center, and fixed party/dex screens.
- Headless dry-run tests for all scenes and transition boundaries.

## Acceptance Criteria

### World & Gameplay
- [ ] Player can walk from Pallet Town through Route 1 and arrive in Viridian City with smooth map transitions.
- [ ] Pokémon Center is a real building with a front door that transitions to an interior room.
- [ ] Nurse Joy NPC at the counter heals the player's party through interactive dialog.
- [ ] NPCs and signposts can be interacted with using `Z`/`Enter`.

### UI & Aesthetics
- [ ] Party screen has zero overlapping text between creature names, levels, and HP bars.
- [ ] Pokédex screen has zero truncated text in header, species list, or bottom prompt.
- [ ] Overworld notification banner fits on screen without text clipping.

### Test Integrity
- [ ] `python3 -m unittest discover tests -v` passes 100% with no regressions.
- [ ] Game runs from `main.py` without crashes across all map boundaries.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*
