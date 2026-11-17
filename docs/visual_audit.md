# Creature Collector — Stage-by-Stage Visual & Mechanics Audit

A critical forensic review of the gameplay stages, world design, UI layout, and mechanics.

---

## 📸 Stage-by-Stage Forensic Review

### Stage 1: Overworld Starting Area
![Overworld Starting Area](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage1_overworld.png)

- **Aesthetic**: The individual 16×16 tiles (textured grass, dirt path, shaded trees, animated water) and trainer walk cycle look good compared to the initial placeholder rectangles.
- **Critical Flaw — Single-Screen Box**: The entire world is literally a single 15×10 grid completely boxed in by solid trees. There is no route out, no path to another city, and no sense of exploration.
- **Critical Flaw — Pokémon Center Placement**: The Pokémon Center is squished against the top boundary row (3 tiles wide, 1 tile tall) and is partially covered by the "Route 1" label.

---

### Stage 2: Pokémon Center "Interaction"
![Pokémon Center Collision and Truncated Notification](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage2_overworld_pokecenter.png)

- **Critical Bug — Fake Building**: There is **no interior** and **no door**. When the player steps into the Pokémon Center, their character is drawn standing directly on top of the building's roof/window.
- **Critical Bug — Broken Notification**: A red banner flashes at the bottom that is cut off: `Healing Center: Party re...`.
- **Verdict**: As the user noticed, the Pokémon Center does not actually work like a real game building. It needs a real door that enters a Pokémon Center interior with Nurse Joy at the counter.

---

### Stage 3 & 4: Battle Screen & Move Selection
![Battle Wild Encounter](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage3_battle_encounter.png)
![Battle Move Selection Grid](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage4_battle_moveselect.png)

- **Strengths**: 3D tiered battle pedestals, 64×64 Pikachu front sprite, Charmander back sprite, notched GBA HP cards with level, current/max HP, and player EXP bar.
- **Flaws**:
  - Battle intro dialog (`WIL...`) lacks an enclosing dialogue panel box during initial slide-in.
  - No move visual particle effects (e.g. claw scratches, flame bursts).

---

### Stage 5: Party Screen (Critical Layout Collision)
![Party Screen Text Overlap](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage5_party.png)

- **Critical Bug — Horizontal Text Collisions**:
  - `CHARMANDER` is 10 characters long. The level `Lv.5` and the HP bar are hardcoded at fixed pixel offsets that collide directly with the name, rendering an unreadable jumble: `CHARMANDERLv.5[HP] 18/18`.
- **Fix Needed**: Column-based layout with dedicated X coordinates for Icon, Name, Level, and HP bar.

---

### Stage 6: Pokédex Screen (Text Truncation)
![Pokédex Text Clipping](/home/psdoom14/.gemini/antigravity/brain/dae5e978-8145-4823-9d72-886ac2d10bf5/screenshots/stage6_pokedex.png)

- **Critical Bug — Severe Text Truncation**:
  - Header: `POKÉDEX  CAUGHT: 1  SEEN:` cuts off the `SEEN` count.
  - List column: `#004 CHARMAND` cuts off the final letters `ER`.
  - Footer: `ESC/X to retu` cuts off the `rn`.
- **Fix Needed**: Expand panel widths, adjust font padding, and use proper column wrapping.

---

## 🗺️ The World Overhaul Roadmap

To fix these flaws and build a real game world:

1. **Multi-Area World Engine**:
   - **Pallet Town** (South starting town with houses and lab)
   - **Route 1** (Winding road with tall grass, ledges, and wild encounters)
   - **Viridian City** (North city with roads, buildings, and Pokémon Center)
   - Seamless edge/warp transitions between maps.
2. **Real Enterable Pokémon Center**:
   - Walk through the door -> interior room with tiled floor, counter, and Nurse Joy.
   - Speak to Nurse Joy with `Z`/`Enter` -> healing sequence -> return to town.
3. **UI Layout Overhaul**:
   - Zero text clipping on Party and Pokédex screens.
