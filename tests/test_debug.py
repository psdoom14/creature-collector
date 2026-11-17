"""Demo helpers: equal-chance wild encounters and the debug menu."""
import json
import os
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model import debug_tools
from src.model.bag import Bag
from src.model.errors import RuleViolation
from src.model.trainer import Party, Trainer
from src.ui import components
from src.ui.debug_scene import DebugScene
from src.ui.engine import GameEngine
from src.ui.evolution_scene import EvolutionScene
from src.ui.overworld_scene import OverworldScene

ROOT = Path(__file__).resolve().parent.parent


class TestEqualEncounters(unittest.TestCase):
    def test_route_1_has_every_species_with_equal_weight(self):
        tables = json.loads((ROOT / "data" / "encounters.json").read_text())
        route = next(t for t in tables if t["route_name"] == "Route 1")
        species = {c["id"] for c in json.loads((ROOT / "data" / "creatures.json").read_text())}
        self.assertEqual({e["creature_id"] for e in route["encounters"]}, species)
        self.assertEqual(len({e["weight"] for e in route["encounters"]}), 1, "all weights equal")

    def test_many_different_species_appear(self):
        loader = DataLoader()
        random.seed(1)
        seen = Counter(loader.get_wild_encounter("Route 1").species_id for _ in range(500))
        self.assertGreaterEqual(len(seen), 20)


class TestDebugTools(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()
        self.trainer = Trainer("A", Party([self.loader.get_creature(4, 5)]), money=1000)

    def test_level_up_learns_new_moves(self):
        mon = self.trainer.party.creatures[0]
        result = debug_tools.level_up(mon, 3, self.loader.get_move)   # 5 -> 8, Ember at 7
        self.assertEqual(mon.level, 8)
        self.assertTrue(mon.knows_move("ember"))
        self.assertIn("ember", result["learned"])

    def test_level_up_stops_at_100(self):
        mon = self.trainer.party.creatures[0]
        debug_tools.level_up(mon, 500, self.loader.get_move)
        self.assertEqual(mon.level, 100)

    def test_add_and_remove_creatures(self):
        where = debug_tools.add_creature(self.trainer, self.loader.get_creature(25, 10))
        self.assertEqual(where, "party")
        self.assertEqual(self.trainer.party.size, 2)
        removed = debug_tools.remove_creature(self.trainer, 1)
        self.assertEqual(removed.species_id, 25)
        with self.assertRaises(RuleViolation):
            debug_tools.remove_creature(self.trainer, 0)   # can't remove the last one

    def test_bag_remove(self):
        bag = Bag([self.loader.get_item("potion", 5)])
        self.assertEqual(bag.remove("potion", 2), 2)
        self.assertEqual(bag.get("potion").quantity, 3)
        self.assertEqual(bag.remove("potion", 99), 3)
        self.assertFalse(bag.has("potion"))
        self.assertEqual(bag.remove("potion", 1), 0)

    def test_money(self):
        debug_tools.change_money(self.trainer, 5000)
        self.assertEqual(self.trainer.money, 6000)
        debug_tools.change_money(self.trainer, -10000)
        self.assertEqual(self.trainer.money, 0, "never below zero")


class TestDebugScene(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.ow = OverworldScene(self.engine)
        self.engine.push_scene(self.ow)
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k):
        self.engine.current_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=""))

    def render(self):
        scene = self.engine.current_scene
        scene.update(0.1)
        scene.draw(self.engine.native_surface)

    def open_debug(self):
        handled = self.engine.handle_global_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
        self.assertTrue(handled)
        self.assertIsInstance(self.engine.current_scene, DebugScene)
        return self.engine.current_scene

    def choose(self, scene, menu, label):
        menu.selected_index = menu.options.index(label) if label in menu.options else \
            next(i for i, o in enumerate(menu.options) if o.startswith(label))
        self.key(pygame.K_z)

    def test_hotkey_only_from_the_overworld(self):
        self.engine.push_scene(DebugScene(self.engine))
        self.assertFalse(self.engine.handle_global_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1)),
                         "no second debug menu on top of the first")

    def test_every_page_renders_without_overflow(self):
        scene = self.open_debug()
        for page in ("LEVEL UP", "ADD CREATURE", "REMOVE CREATURE", "ITEMS", "MONEY"):
            self.choose(scene, scene.menu, page)
            self.render()
            self.key(pygame.K_x)
            self.render()
        self.assertEqual(components.overflow_log(), [])

    def test_level_up_then_evolve_on_close(self):
        mon = self.engine.game_state.trainer.party.creatures[0]   # Charmander Lv5
        scene = self.open_debug()
        self.choose(scene, scene.menu, "LEVEL UP")
        self.key(pygame.K_z)                    # pick the first creature
        self.choose(scene, scene.sub_menu, "+10")
        self.choose(scene, scene.sub_menu, "+10")
        self.assertEqual(mon.level, 25)
        self.key(pygame.K_x)
        self.key(pygame.K_x)
        self.key(pygame.K_x)                    # close the debug menu
        self.assertIsInstance(self.engine.current_scene, EvolutionScene)

    def test_add_a_creature_at_a_chosen_level(self):
        party = self.engine.game_state.trainer.party
        scene = self.open_debug()
        self.choose(scene, scene.menu, "ADD CREATURE")
        scene.list_menu.selected_index = 24          # last species
        for _ in range(5):
            self.key(pygame.K_RIGHT)                  # level 5 -> 10
        self.key(pygame.K_z)
        self.assertEqual(party.size, 2)
        self.assertEqual(party.creatures[1].level, 10)
        self.assertTrue(self.engine.game_state.pokedex.is_caught(party.creatures[1].species_id))

    def test_items_and_money(self):
        trainer = self.engine.game_state.trainer
        scene = self.open_debug()
        self.choose(scene, scene.menu, "ITEMS")
        ids = [it["id"] for it in scene.item_catalog]
        scene.list_menu.selected_index = ids.index("ultra_ball")
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_z)                          # +10
        self.assertEqual(trainer.get_item("ultra_ball").quantity, 11)
        scene.list_menu.selected_index = ids.index("potion")
        self.key(pygame.K_DELETE)                     # remove them all
        self.assertFalse(trainer.has_item("potion"))
        self.key(pygame.K_x)
        money = trainer.money
        self.choose(scene, scene.menu, "MONEY")
        self.choose(scene, scene.sub_menu, "+10000")
        self.assertEqual(trainer.money, money + 10000)


if __name__ == "__main__":
    unittest.main()
