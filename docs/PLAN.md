# Creature Collector — Critical Review & Build Plan

College OOP project: a small GBA-style creature collector demo.
Target scope: professor intro + starter choice, a few creatures with level-ups, evolutions and move learning, wild and trainer battles, 2 towns + 1 route (stretch: 3rd town), 1 gym (stretch: 2nd).

Reviewed 2026-11-17 against commit `3054041`. 37/37 tests pass, `src/model/` has no pygame imports.

---

## Part 1 — Critical flaws

### A. Bugs (gameplay is wrong today)

| # | Bug | Where | Verified |
|---|-----|-------|----------|
| B1 | **Crash** when the wild creature runs out of PP: `MoveFactory` is used for Struggle but never imported → `NameError` | `src/model/battle.py:339` | ✅ reproduced |
| B2 | **Healing center can't revive fainted creatures.** `heal_all()` calls `heal()`, which returns 0 for fainted creatures | `src/model/trainer.py:57` | ✅ by reading |
| B3 | **Sleep never ends.** No turn counter, no wake-up roll — a sleeping creature is stuck forever | `battle.py:_execute_move_step` | ✅ by reading |
| B4 | **Evolution never happens in the graphical game.** `can_evolve()` is only checked in `terminal_demo.py` | `battle_scene.py` | ✅ |
| B5 | **New moves are announced but never learned.** `unlocked_moves` produces a message only; `learn_move()` is never called | `battle.py:_award_victory_xp` | ✅ |
| B6 | **Caught creature disappears when party is full.** Event says "storage", but no storage exists | `battle.py:462` | ✅ |
| B7 | **Can't switch creatures in battle.** POKÉMON menu says "already fighting"; after a faint the next creature silently takes over with no "Go!" or sprite refresh | `battle_scene.py:161`, `trainer.py:46` | ✅ |
| B8 | **Using an item in battle is a free turn**, and the UI calls `trainer.use_item()` directly, bypassing `Battle` | `battle_scene.py:192` | ✅ |
| B9 | **Blacking out does nothing** — no return to the healing center, no heal | `battle_scene.py` | ✅ |
| B10 | **Save exists, Load doesn't.** `SaveManager.load_game()` is never called; no title screen / Continue | `main.py`, `overworld_scene.py` | ✅ |
| B11 | **Battle UI matches creatures by name.** Wild Charmander vs your Charmander → HP bar / faint animation hits the wrong side | `battle_scene.py:90-100` | ✅ by reading |
| B12 | `GrassCreature.apply_status` says it resists poison/sleep but the branch is `pass` | `creature.py:275` | ✅ |
| B13 | Party and Pokédex text overlap / clipping; location banner covers the healing center | `party_scene.py`, `pokedex_scene.py`, `overworld_scene.py` | ✅ screenshots |
| B14 | Bag shows only the first 4 items in battle; overworld BAG is just a notification; EXIT does nothing | `battle_scene.py:153`, `overworld_scene.py` | ✅ |

### B. OOP design flaws (what a grader will notice)

**Encapsulation — weak**
- `Creature.current_hp`, `level`, `xp`, `moves`, `status_effect`, `stats`, `stat_stages` are public and writable.
- `Item.quantity`, `Trainer.inventory`, `Party.creatures`, `Pokedex.seen/caught` are public collections; `Battle` reaches in and does `del self.player.inventory[ball_id]`.
- `GameState.badges` is a bare int; `current_route` is one string used for map name, HUD label *and* encounter-table key.

**Polymorphism — half there**
- Real: `item.use()`, `scene.update()/draw()`, `move.is_damaging()`.
- Faked with type checks: `if move.category == "special"` (`battle.py:80`), `isinstance(item, CatchBall)` (`battle.py:436`, `battle_scene.py:187`), status handled by `if status == "sleep" / "paralyze" / "burn"` chains in 4 places, move effects by a string `if/elif` chain (`_apply_move_effect`), event types are raw strings compared in the UI.

**Inheritance — wrong axis in one place**
- `FireCreature`/`WaterCreature`/… subclass by *primary type*. That breaks for dual types (Grass/Poison, Fire/Flying), `WaterCreature` and `NormalCreature` are empty `pass` classes, and Rock/Ghost/Poison have no class at all. A creature's type is **data**, not an *is-a* relationship.
- Meanwhile the places that *should* use inheritance don't: there's only one `Battle` (wild-only — no trainer/gym battles possible), no `Character`/`NPC` hierarchy, statuses are strings.

**Abstraction — good, but leaky in places**
- Good: `Item`, `Move`, `Scene` are ABCs; `Battle` emits events instead of drawing.
- Leaky: the overworld map, collision rules and encounter logic live inside the **UI** class `OverworldScene` (hard-coded `MAP_DATA`), violating the project's own "model has the rules, data in JSON" principle. The EXP-bar formula is duplicated in the UI as `level ** 3` instead of calling the model.

**Code quality**
- The "check who fainted → won/lost/switch" block is copy-pasted 4 times in `battle.py`.
- `Pokedex.get_completion(total_species=25)` hard-codes the species count.
- Test coverage of the model is thin: 4 battle tests, 4 creature tests, 1 save test. Most of the 37 tests check assets and rendering.

---

## Part 2 — Target design (the 4 pillars)

### Encapsulation
- `Creature`: private `_hp`, `_level`, `_xp`, `_moves`, `_status`; read-only properties; state changes only via `take_damage()`, `heal()`, `gain_xp()`, `learn_move()`, `set_status()`.
- New `Bag` class owns items (`add`, `remove`, `consume`, `items_of(kind)`); `Trainer` exposes a `Bag`, not a dict.
- `Party` keeps `_creatures` private, exposes iteration/`lead`/`swap`; new `PCBox` storage for overflow catches.
- `Pokedex` private sets; `GameState` gets a `BadgeCase` and a `Location(map_id, x, y)`.

### Abstraction (abstract base classes)
- `StatusCondition`, `MoveEffect`, `Battle`, `BattleAI`, `Interactable`, plus existing `Item`, `Move`, `Scene`.

### Inheritance (real *is-a* trees)
```
StatusCondition ─┬─ Burn  ─ Poison ─ Paralysis ─ Sleep
Move ────────────┬─ PhysicalMove ─ SpecialMove ─ StatusMove
MoveEffect ──────┬─ InflictStatus ─ HealUser ─ ChangeStat
Item (existing) ─┬─ HealingItem ─ ReviveItem ─ StatusCureItem ─ CatchBall
Battle ──────────┬─ WildBattle
                 └─ TrainerBattle ── GymBattle
BattleAI ────────┬─ RandomAI ─ SmartAI (picks super-effective moves)
Character ───────┬─ Player
                 └─ NPC ─┬─ TrainerNPC ── GymLeader
                         ├─ Professor
                         └─ Healer (healing-center nurse)
Interactable ────┬─ NPC ─ Sign ─ Warp/Door
Scene (existing) ┬─ Title ─ ProfessorIntro ─ StarterSelect ─ Overworld ─ Battle ─ Evolution ─ Party ─ Pokédex ─ Bag
```
Type-based `Creature` subclasses are removed; type immunities move into `StatusCondition.can_afflict(creature)` (e.g. `Burn` refuses Fire types).

### Polymorphism (one call, many behaviours)
- `move.attack_stat(user)` / `move.defense_stat(target)` — Physical vs Special. Removes `category ==`.
- `status.can_act()`, `status.on_turn_end()`, `status.speed_modifier`, `status.catch_bonus` — removes all status `if` chains; fixes sleep (B3).
- `effect.apply(user, target) -> events` — replaces the string `if/elif` chain.
- `item.use_in_battle(battle, target) -> events` — `CatchBall` overrides it; removes `isinstance` (B8).
- `battle.can_flee()`, `battle.can_catch()`, `battle.on_victory()` — wild vs trainer vs gym (gym awards a badge).
- `ai.choose_move(creature, opponent)` — wild creatures random, gym leader smart.
- `interactable.interact(player, world) -> Action` — sign shows text, healer heals, trainer starts a battle, door warps.

---

## Part 3 — Build plan (each phase ends with all tests green and a commit)

| Phase | Work | Fixes |
|---|---|---|
| **0. Safety net** | Write failing tests that reproduce B1–B6, B12 first | — |
| **1. Model refactor (pillars)** | Encapsulate `Creature`, `Item`, `Party`, `Pokedex`; add `Bag`, `PCBox`; `PhysicalMove`/`SpecialMove`; `StatusCondition` tree; `MoveEffect` tree; remove type subclasses; dedupe faint handling; `BattleEvent.type` → `Enum`. No visible gameplay change | B1, B2, B3, B6, B12 |
| **2. Battle completeness** | `Battle` ABC → `WildBattle`; items cost a turn via `use_in_battle`; switch menu; move-learning prompt (replace a move if 4 known); `EvolutionScene`; blackout → warp to last healer; events carry creature *ids*, not names | B4, B5, B7, B8, B9, B11, B14 |
| **3. UI fixes + title** | Column layout for Party, Pokédex widths, banner placement; Title screen with New Game / Continue (load) | B10, B13 |
| **4. World model** | `WorldMap` + `Location` in the **model**, maps in `data/maps/*.json` (tiles, collision, warps, encounter zone, entities); camera scrolling for maps larger than one screen; `Interactable` entities (`Sign`, `Door`, `Healer`); enterable healing center interior | world flaws |
| **5. Story start** | `Professor` NPC intro dialogue, name entry (optional), `StarterSelectScene` (pick 1 of 3), rival takes the counter-type | — |
| **6. Trainers & gym** | `TrainerBattle`, `TrainerNPC` with line-of-sight trigger, `GymBattle` + `GymLeader` + `SmartAI`, `BadgeCase`, prize money | — |
| **7. Polish & report** | Evolution animation polish, optional sounds, `docs/OOP.md` mapping every pillar to file:line, UML class diagram, final screenshots | — |

### Progress

**Phases 0–1 done (2026-11-17).** 58 tests pass (37 original + 6 bug regressions + 15 OOP pillar tests).
- Fixed: B1 (Struggle crash), B2 (healing revives fainted + restores PP), B3 (sleep lasts 1–3 turns), B6 (full party → PC box), B12 (type immunities work for every type, including dual types). B8 also fixed early: items in battle go through `Battle.use_item()` and cost a turn.
- New files: `src/model/events.py`, `status.py`, `move_effect.py`, `bag.py`; `tests/test_bug_regressions.py`, `tests/test_oop_pillars.py`.
- API changes: type-based `Creature` subclasses removed; `Creature.evolve()` now changes the creature in place; `Trainer.inventory` → `Trainer.bag`; `Pokedex.get_completion()` needs the species total.

### Demo world (original names to be decided)
- **Town 1** — player's home, professor's lab, exit north.
- **Route** — tall grass, a couple of trainers, signs.
- **Town 2** — healing center (enterable), shop (stretch), **Gym 1**.
- Stretch: second route + Town 3 + Gym 2.

### Ground rules kept throughout
- `grep -rn pygame src/model/` stays at 0.
- Game data lives in `data/*.json`, never hard-coded in classes.
- Every phase adds tests; nothing merges with a red suite.
