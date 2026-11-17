import os
import sys
from pathlib import Path

# Run from anywhere: put the project root on the import path and work from there.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Ensure headless pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["LC_ALL"] = "C.UTF-8"

import pygame

from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.battle_scene import BattleScene
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene

def main():
    engine = GameEngine(title="Capture Stages")
    
    # 1. Capture Overworld Initial
    overworld = OverworldScene(engine)
    engine.push_scene(overworld)
    overworld.update(0.1)
    overworld.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage1_overworld.png")
    print("Saved screenshots/stage1_overworld.png")
    
    # 2. Capture the healing center interior, talking to the nurse
    from src.model.direction import Direction
    from src.model.world import Location
    overworld.teleport(Location("healing_center", 5, 3), Direction.UP)
    overworld.location_timer = 0
    overworld.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
    overworld.update(2.0)
    overworld.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage2_healing_center.png")
    print("Saved screenshots/stage2_healing_center.png")
    
    overworld.mode = "WALK"

    # 3. Capture Battle Start (Wild Pikachu)
    wild_pika = engine.data_loader.get_creature(25, level=5) # Pikachu
    battle_scene = BattleScene(engine, wild_pika)
    engine.push_scene(battle_scene)
    battle_scene.update(0.1)
    battle_scene.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage3_battle_encounter.png")
    print("Saved screenshots/stage3_battle_encounter.png")
    
    # 4. Capture Battle Move Select
    battle_scene.sub_state = "ACTION_SELECT"
    battle_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
    battle_scene.update(0.1)
    battle_scene.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage4_battle_moveselect.png")
    print("Saved screenshots/stage4_battle_moveselect.png")

    # 5. Capture Party Scene
    party_scene = PartyScene(engine)
    engine.push_scene(party_scene)
    party_scene.update(0.1)
    party_scene.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage5_party.png")
    print("Saved screenshots/stage5_party.png")

    # 6. Capture Pokedex Scene
    pokedex_scene = PokedexScene(engine)
    engine.push_scene(pokedex_scene)
    pokedex_scene.update(0.1)
    pokedex_scene.draw(engine.native_surface)
    scaled = pygame.transform.scale(engine.native_surface, (720, 480))
    pygame.image.save(scaled, "screenshots/stage6_pokedex.png")
    print("Saved screenshots/stage6_pokedex.png")
    
    print("All stages captured successfully!")

if __name__ == "__main__":
    main()
