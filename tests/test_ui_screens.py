"""Phase 3: menu screens fit their text, title screen, save/continue, bag screen.

See docs/PLAN.md bugs B10, B13, B14.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.model.game_state import GameState
from src.model.world import Location
from src.save_manager import SaveManager
from src.ui import components
from src.ui.bag_scene import BagScene
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene
from src.ui.title_scene import TitleScene


def press(scene, key):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


class _EngineTest(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.loader = self.engine.data_loader
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, scene, frames=2):
        for _ in range(frames):
            scene.update(0.5)
            scene.draw(self.engine.native_surface)

    def assertNoOverflow(self):
        self.assertEqual(components.overflow_log(), [], "text drawn wider than its box")


class TestTextFits(_EngineTest):
    def test_fit_helper_shrinks_then_reports(self):
        font = components.get_font(10)
        surf = pygame.Surface((240, 160))
        components.draw_fitted_text(surf, "CHARMANDER", 0, 0, max_width=70, font=font)
        self.assertNoOverflow()
        components.draw_fitted_text(surf, "X" * 80, 0, 0, max_width=40, font=font)
        self.assertEqual(len(components.overflow_log()), 1)

    def test_party_screen_fits_six_long_names(self):
        party = self.engine.game_state.trainer.party
        for species in (5, 8, 2, 6, 9):           # Charmeleon, Wartortle, Ivysaur, Charizard, Blastoise
            party.add(self.loader.get_creature(species, level=100))
        party.creatures[1].take_damage(9999)       # one fainted
        scene = PartyScene(self.engine)
        self.engine.push_scene(scene)
        for _ in range(6):
            self.render(scene)
            press(scene, pygame.K_DOWN)
        self.assertNoOverflow()

    def test_pokedex_fits_every_species(self):
        dex = self.engine.game_state.pokedex
        for sp in self.loader.get_all_species():
            dex.register_caught(sp["id"])
        scene = PokedexScene(self.engine)
        self.engine.push_scene(scene)
        for _ in range(len(scene.species_list)):
            self.render(scene, frames=1)
            press(scene, pygame.K_DOWN)
        self.assertNoOverflow()

    def test_overworld_notification_and_location_fit(self):
        ow = OverworldScene(self.engine)
        self.engine.push_scene(ow)
        self.engine.game_state.current_route = "Viridian Forest"
        ow.show_location_banner()
        ow.show_notification("Healing Center: Your party has been fully restored to health!")
        self.render(ow)
        self.assertNoOverflow()

    def test_location_banner_hides_after_a_few_seconds(self):
        ow = OverworldScene(self.engine)
        self.engine.push_scene(ow)
        self.assertTrue(ow.location_banner_visible)
        for _ in range(10):
            ow.update(0.5)
        self.assertFalse(ow.location_banner_visible)


class TestSaveAndTitle(_EngineTest):
    def test_title_without_save_offers_only_new_game(self):
        title = TitleScene(self.engine)
        self.engine.push_scene(title)
        self.assertNotIn("CONTINUE", title.options)
        self.assertIn("NEW GAME", title.options)
        self.render(title)
        self.assertNoOverflow()

    def test_save_then_continue_restores_progress_and_position(self):
        ow = OverworldScene(self.engine)
        self.engine.push_scene(ow)
        ow.player_x, ow.player_y = 3, 8
        trainer = self.engine.game_state.trainer
        trainer.earn(321)
        money = trainer.money
        self.assertTrue(ow.save_game())

        fresh = GameEngine(save_path=self.engine.save_path)
        title = TitleScene(fresh)
        fresh.push_scene(title)
        self.assertEqual(title.options[0], "CONTINUE")
        press(title, pygame.K_RETURN)  # skip "press start"
        title.menu.selected_index = 0
        press(title, pygame.K_RETURN)

        ow2 = fresh.current_scene
        self.assertIsInstance(ow2, OverworldScene)
        self.assertEqual((ow2.player_x, ow2.player_y), (3, 8))
        self.assertEqual(fresh.game_state.trainer.money, money)

    def test_new_game_starts_fresh_even_with_a_save(self):
        self.engine.game_state.trainer.earn(5000)
        SaveManager.save_game(self.engine.game_state, self.engine.save_path)

        fresh = GameEngine(save_path=self.engine.save_path)
        title = TitleScene(fresh)
        fresh.push_scene(title)
        press(title, pygame.K_RETURN)
        title.menu.selected_index = title.options.index("NEW GAME")
        press(title, pygame.K_RETURN)

        self.assertIsInstance(fresh.current_scene, OverworldScene)
        self.assertLess(fresh.game_state.trainer.money, 5000)

    def test_game_state_round_trips_position_and_play_time(self):
        gs = self.engine.game_state
        gs.location = Location("fernvale_town", 4, 5)
        gs.add_play_time(75.5)
        data = gs.to_dict()
        loaded = GameState.from_dict(data, self.loader)
        self.assertEqual(loaded.location, Location("fernvale_town", 4, 5))
        self.assertAlmostEqual(loaded.play_time, 75.5)


class TestBagScene(_EngineTest):
    def open_bag(self):
        bag = BagScene(self.engine)
        self.engine.push_scene(bag)
        return bag

    def select_item(self, bag, item_id):
        ids = [it.id for it in self.engine.game_state.trainer.bag.items]
        bag.menu.selected_index = ids.index(item_id)
        press(bag, pygame.K_RETURN)

    def test_potion_heals_a_chosen_creature(self):
        trainer = self.engine.game_state.trainer
        mon = trainer.party.creatures[0]
        mon.take_damage(10)
        before = trainer.get_item("potion").quantity

        bag = self.open_bag()
        self.select_item(bag, "potion")
        self.assertEqual(bag.mode, "CHOOSE_TARGET")
        press(bag, pygame.K_RETURN)                # first party slot

        self.assertEqual(mon.current_hp, mon.max_hp)
        self.assertEqual(trainer.get_item("potion").quantity, before - 1)
        self.render(bag)
        self.assertNoOverflow()

    def test_balls_cannot_be_used_outside_battle(self):
        trainer = self.engine.game_state.trainer
        before = trainer.get_item("poke_ball").quantity
        bag = self.open_bag()
        self.select_item(bag, "poke_ball")
        self.assertEqual(bag.mode, "MESSAGE")
        self.assertEqual(trainer.get_item("poke_ball").quantity, before)

    def test_items_say_whether_they_work_outside_battle(self):
        self.assertTrue(self.loader.get_item("potion").usable_in_field)
        self.assertFalse(self.loader.get_item("poke_ball").usable_in_field)


if __name__ == "__main__":
    unittest.main()
