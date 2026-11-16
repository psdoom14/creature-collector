"""Playable terminal prototype of the Creature Collector game."""
import sys
import time
from typing import Optional

from src.data_loader import DataLoader
from src.model.trainer import Trainer, Party
from src.model.pokedex import Pokedex
from src.model.battle import Battle, BattleState
from src.model.game_state import GameState
from src.save_manager import SaveManager


def render_hp_bar(current: int, maximum: int, length: int = 15) -> str:
    """Render a visual ASCII HP bar."""
    pct = max(0.0, min(1.0, current / max(1, maximum)))
    filled = int(length * pct)
    empty = length - filled
    bar = "█" * filled + "░" * empty

    # Color hints in terminal
    if pct > 0.5:
        color = "\033[92m"  # Green
    elif pct > 0.2:
        color = "\033[93m"  # Yellow
    else:
        color = "\033[91m"  # Red
    reset = "\033[0m"

    return f"{color}[{bar}]{reset} {current}/{maximum} HP"


def print_status_box(enemy, player):
    """Draw a GBA-style battle layout in ASCII."""
    print("\n" + "=" * 54)
    # Enemy box (top right)
    e_status = f" [{enemy.status_effect.upper()}]" if enemy.status_effect else ""
    print(f"  {enemy.name.upper():<16} Lv.{enemy.level:<3}{e_status}")
    print(f"  {render_hp_bar(enemy.current_hp, enemy.max_hp)}")
    print("-" * 54)

    # Player box (bottom left)
    if player:
        p_status = f" [{player.status_effect.upper()}]" if player.status_effect else ""
        print(f"  {player.name.upper():<16} Lv.{player.level:<3}{p_status}")
        print(f"  {render_hp_bar(player.current_hp, player.max_hp)}")
    print("=" * 54)


def play_battle(battle: Battle, auto_input: Optional[list] = None) -> bool:
    """Run an interactive or automated combat loop."""
    input_idx = 0

    def get_choice(prompt: str) -> str:
        nonlocal input_idx
        if auto_input is not None:
            if input_idx < len(auto_input):
                val = str(auto_input[input_idx])
                input_idx += 1
                print(f"{prompt}{val}")
                return val
            return "1"  # Default fight
        try:
            return input(prompt).strip()
        except EOFError:
            return "4"  # Default run

    p_lead = battle.player_creature
    w_creature = battle.wild_creature
    print(f"\n⚡ Wild {w_creature.name} (Lv.{w_creature.level}) appeared! ⚡")
    print(f"Go! {p_lead.name}!")

    while battle.is_active:
        print_status_box(w_creature, battle.player_creature)

        if battle.state == BattleState.SELECTING_SWITCH:
            print("\nChoose next creature:")
            for i, c in enumerate(battle.player.party.creatures):
                status_str = " (FAINTED)" if c.is_fainted else f" {c.current_hp}/{c.max_hp} HP"
                print(f"  [{i+1}] {c.name} Lv.{c.level}{status_str}")
            sel = get_choice("Switch to: ")
            try:
                idx = int(sel) - 1
                events = battle.switch_creature(idx)
                for e in events:
                    print(f"  > {e.message}")
            except ValueError:
                pass
            continue

        print("\nWhat will you do?")
        print("  [1] Fight    [2] Bag    [3] Pokémon    [4] Run")
        act = get_choice("Select action (1-4): ")

        if act == "1":  # FIGHT
            cur = battle.player_creature
            if not cur:
                break
            print("\nChoose a move:")
            for i, m in enumerate(cur.moves):
                print(f"  [{i+1}] {m.name:<14} ({m.type:<8}) PP: {m.current_pp}/{m.max_pp}")
            print("  [5] Back")
            m_sel = get_choice("Select move: ")
            if m_sel == "5":
                continue
            try:
                m_idx = int(m_sel) - 1
                events = battle.execute_move(m_idx)
                for e in events:
                    print(f"  > {e.message}")
            except ValueError:
                print("Invalid input.")

        elif act == "2":  # BAG
            items = list(battle.player.inventory.values())
            if not items:
                print("  Bag is empty!")
                continue
            print("\nItems in Bag:")
            for i, it in enumerate(items):
                print(f"  [{i+1}] {it.name:<16} x{it.quantity} - {it.description}")
            print("  [0] Back")
            b_sel = get_choice("Choose item: ")
            if b_sel == "0":
                continue
            try:
                b_idx = int(b_sel) - 1
                if 0 <= b_idx < len(items):
                    chosen_item = items[b_idx]
                    if chosen_item.item_type == "catch":
                        events = battle.attempt_catch(chosen_item.id)
                        for e in events:
                            print(f"  > {e.message}")
                    else:
                        target = battle.player_creature
                        res = battle.player.use_item(chosen_item.id, target)
                        print(f"  > {res}")
            except ValueError:
                print("Invalid choice.")

        elif act == "3":  # POKEMON PARTY
            print("\nParty:")
            for i, c in enumerate(battle.player.party.creatures):
                print(f"  [{i+1}] {c.name:<12} Lv.{c.level:<2} {c.current_hp}/{c.max_hp} HP")
            print("  [0] Back")
            p_sel = get_choice("Switch to (or 0 to back): ")
            if p_sel != "0":
                try:
                    events = battle.switch_creature(int(p_sel) - 1)
                    for e in events:
                        print(f"  > {e.message}")
                except ValueError:
                    pass

        elif act == "4":  # RUN
            events = battle.attempt_run()
            for e in events:
                print(f"  > {e.message}")

    # Check evolution for party members after battle
    for c in battle.player.party.creatures:
        if c.can_evolve():
            print(f"\n✨ What? {c.name} is evolving! ✨")
            evo_id = c.evolution["into"]
            loader = DataLoader()
            new_data = loader.get_species_data(evo_id)
            if new_data:
                evolved = c.evolve(new_data)
                # Replace in party
                idx = battle.player.party.creatures.index(c)
                battle.player.party.creatures[idx] = evolved
                print(f"🎉 Congratulations! Your {c.name} evolved into {evolved.name}! 🎉")

    return battle.state == BattleState.WON or battle.state == BattleState.CAUGHT


def main():
    """Main terminal loop."""
    loader = DataLoader()
    chart = loader.get_type_chart()

    print("\n" + "=" * 54)
    print("      POKÉMON RETRO CREATURE COLLECTOR (OOP)")
    print("=" * 54)

    # Starter selection
    print("\nChoose your Starter Pokémon:")
    print("  [1] Charmander (Fire)")
    print("  [2] Squirtle   (Water)")
    print("  [3] Bulbasaur  (Grass/Poison)")

    starter_map = {"1": 4, "2": 7, "3": 1}
    auto = ("--auto" in sys.argv)
    choice = "1" if auto else input("Enter choice (1-3): ").strip()
    species_id = starter_map.get(choice, 4)

    starter = loader.get_creature(species_id, level=5)
    party = Party([starter])
    trainer = Trainer("Player", party)

    # Starting items
    trainer.add_item(loader.get_item("poke_ball", quantity=10), 10)
    trainer.add_item(loader.get_item("potion", quantity=5), 5)

    pokedex = Pokedex()
    pokedex.register_caught(starter.species_id)

    game_state = GameState(trainer, pokedex, current_route="Route 1")

    print(f"\nReceived {starter.name}! Poké Balls x10, Potions x5 added to bag.")

    routes = ["Route 1", "Route 2", "Viridian Forest", "Mt. Moon"]
    route_idx = 0

    running = True
    auto_rounds = 3 if auto else 999999
    round_count = 0

    while running and round_count < auto_rounds:
        round_count += 1
        current_route = routes[route_idx]
        print(f"\n📍 Exploring {current_route}...")

        wild = loader.get_wild_encounter(current_route)
        if not wild:
            wild = loader.get_creature(19, level=3)

        pokedex.register_seen(wild.species_id)
        battle = Battle(trainer, wild, chart)

        if auto:
            # Automated sequence: fight with move 1, or catch if low HP
            auto_actions = ["1", "1", "1", "1"]
            play_battle(battle, auto_input=auto_actions)
        else:
            play_battle(battle)

        # After encounter options
        if trainer.party.all_fainted():
            print("\nAll your creatures have fainted! Hurrying to Pokémon Center...")
            trainer.party.heal_all()
            print("Party restored to full vitality!")

        print("\nOptions:")
        print("  [1] Continue Exploring")
        print("  [2] Heal Party")
        print("  [3] Check Pokédex")
        print("  [4] Save Game")
        print("  [5] Change Route")
        print("  [6] Quit")

        next_act = "1" if auto else input("Action (1-6): ").strip()
        if next_act == "2":
            trainer.party.heal_all()
            print("Party completely healed!")
        elif next_act == "3":
            c_cnt, tot, pct = pokedex.get_completion(23)
            print(f"\n📖 POKÉDEX: {c_cnt}/{tot} species caught ({pct}%)")
            for sp in loader.get_all_species():
                st = "✓ CAUGHT" if pokedex.is_caught(sp["id"]) else ("? SEEN" if pokedex.is_seen(sp["id"]) else "  UNKNOWN")
                print(f"  #{sp['id']:03d} {sp['name']:<14} {st}")
        elif next_act == "4":
            SaveManager.save_game(game_state, "savegame.json")
            print("💾 Game saved successfully to savegame.json!")
        elif next_act == "5":
            route_idx = (route_idx + 1) % len(routes)
            game_state.current_route = routes[route_idx]
            print(f"Traveled to {routes[route_idx]}!")
        elif next_act == "6":
            running = False

    print("\nThanks for playing!")


if __name__ == "__main__":
    main()
