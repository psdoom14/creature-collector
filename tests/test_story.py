"""Phase 5: professor intro, name entry, choosing a starter, the rival's pick, the route gate."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model.direction import Direction
from src.model.entities import NPC, Professor, StarterBall
from src.model.game_state import GameState
from src.model.story import StoryFlags, give_starter, pick_rival_starter
from src.model.trainer import Party, Trainer
from src.model.world import Explorer, Location, World, WorldMap
from src.ui import components
from src.ui.engine import GameEngine
from src.ui.intro_scene import IntroScene
from src.ui.overworld_scene import OverworldScene
from src.ui.title_scene import TitleScene

STARTERS = (4, 7, 1)  # fire, water, grass


def fresh_state(loader):
    return GameState(Trainer("ALEX", Party([])))


class TestStoryModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()
        cls.species = {sid: cls.loader.get_species_data(sid)["types"] for sid in STARTERS}

    def test_flags(self):
        flags = StoryFlags()
        self.assertFalse(flags.has("has_starter"))
        flags.set("has_starter")
        self.assertTrue(flags.has("has_starter"))
        self.assertEqual(StoryFlags.from_list(flags.to_list()).to_list(), ["has_starter"])

    def test_rival_picks_the_type_that_beats_yours(self):
        self.assertEqual(pick_rival_starter(4, self.species, self.chart), 7)   # fire -> water
        self.assertEqual(pick_rival_starter(7, self.species, self.chart), 1)   # water -> grass
        self.assertEqual(pick_rival_starter(1, self.species, self.chart), 4)   # grass -> fire

    def test_give_starter_updates_party_dex_flags_and_rival(self):
        state = fresh_state(self.loader)
        mon = self.loader.get_creature(4, level=5)
        give_starter(state, mon, rival_species=7)
        self.assertEqual(state.trainer.party.creatures, (mon,))
        self.assertTrue(state.pokedex.is_caught(4))
        self.assertTrue(state.flags.has("has_starter"))
        self.assertTrue(state.flags.has("starter_taken_4"))
        self.assertTrue(state.flags.has("starter_taken_7"))
        self.assertEqual(state.rival_starter, 7)

    def test_starter_ball_offers_until_taken(self):
        state = fresh_state(self.loader)
        ball = StarterBall(3, 3, species_id=4)
        offer = ball.interact(state, Direction.UP)
        self.assertEqual(offer.effect, "offer_starter")
        self.assertEqual(offer.data["species_id"], 4)
        state.flags.set("starter_taken_4")
        self.assertIsNone(ball.interact(state, Direction.UP).effect)
        self.assertFalse(ball.is_present(state))

    def test_professor_changes_lines_and_gives_balls_once(self):
        state = fresh_state(self.loader)
        prof = Professor(5, 1, "PROF. CEDAR", lines=["Pick one!"], after_lines=["Good luck!"],
                         gift={"poke_ball": 5})
        self.assertIsInstance(prof, NPC)
        self.assertEqual(prof.interact(state, Direction.UP).lines, ("Pick one!",))
        state.flags.set("has_starter")
        first = prof.interact(state, Direction.UP)
        self.assertEqual(first.effect, "give_items")
        self.assertEqual(first.data["items"], {"poke_ball": 5})
        second = prof.interact(state, Direction.UP)
        self.assertIsNone(second.effect)
        self.assertEqual(second.lines, ("Good luck!",))

    def test_gated_warp_blocks_until_flag_is_set(self):
        m = WorldMap.from_dict({
            "id": "a", "name": "A", "legend": {",": "path", "T": "tree"},
            "rows": ["T,T", "T,T", "T,T"],
            "warps": [{"x": 1, "y": 0, "to": "a", "tx": 1, "ty": 2, "facing": "down",
                       "requires": "has_starter", "blocked_lines": ["Not yet!"]}],
        })
        state = fresh_state(self.loader)
        ex = Explorer(World([m]), Location("a", 1, 1), Direction.UP, flags=state.flags)
        result = ex.step(Direction.UP)
        self.assertFalse(result.moved)
        self.assertEqual(result.blocked_lines, ("Not yet!",))
        state.flags.set("has_starter")
        self.assertTrue(ex.step(Direction.UP).warped)

    def test_flags_and_rival_survive_save(self):
        state = fresh_state(self.loader)
        state.flags.set("has_starter")
        state.rival_starter = 7
        loaded = GameState.from_dict(state.to_dict(), self.loader)
        self.assertTrue(loaded.flags.has("has_starter"))
        self.assertEqual(loaded.rival_starter, 7)

    def test_lab_and_gate_exist_in_shipped_world(self):
        world = self.loader.load_world()
        lab = world.get("professor_lab")
        balls = [e for e in lab.entities if isinstance(e, StarterBall)]
        self.assertEqual(sorted(b.species_id for b in balls), sorted(STARTERS))
        self.assertTrue(any(isinstance(e, Professor) for e in lab.entities))
        town = world.get("fernvale_town")
        gated = [w for w in town.warps if w.target.map_id == "route_1"]
        self.assertTrue(gated and all(w.required_flag == "has_starter" for w in gated))


class _UITest(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k, unicode=""):
        self.engine.current_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=unicode))

    def frames(self, n=1, dt=1.0):
        for _ in range(n):
            scene = self.engine.current_scene
            scene.update(dt)
            scene.draw(self.engine.native_surface)

    def type_text(self, text):
        for ch in text:
            self.key(getattr(pygame, f"K_{ch.lower()}"), unicode=ch)


class TestNewGameFlow(_UITest):
    def start_new_game(self):
        title = TitleScene(self.engine)
        self.engine.push_scene(title)
        self.key(pygame.K_RETURN)
        title.menu.selected_index = title.options.index("NEW GAME")
        self.key(pygame.K_RETURN)

    def play_intro(self, name="ALEX"):
        intro = self.engine.current_scene
        self.assertIsInstance(intro, IntroScene)
        for _ in range(40):
            if self.engine.current_scene is not intro:
                break
            self.frames()
            if intro.mode == "NAME":
                self.type_text(name)
                self.frames()
                self.key(pygame.K_RETURN)
            else:
                self.key(pygame.K_z)

    def test_new_game_runs_the_intro_and_names_the_player(self):
        self.start_new_game()
        self.play_intro("ALEX")
        ow = self.engine.current_scene
        self.assertIsInstance(ow, OverworldScene)
        state = self.engine.game_state
        self.assertEqual(state.trainer.name, "ALEX")
        self.assertEqual(state.trainer.party.size, 0)
        self.assertEqual(ow.explorer.location, self.engine.data_loader.start_location())
        self.assertEqual(components.overflow_log(), [])

    def test_name_entry_needs_a_letter_and_has_a_limit(self):
        self.start_new_game()
        intro = self.engine.current_scene
        while intro.mode != "NAME":
            self.frames()
            self.key(pygame.K_z)
        self.key(pygame.K_RETURN)
        self.assertEqual(intro.mode, "NAME", "empty name is not accepted")
        self.type_text("ABCDEFGHIJKL")
        self.assertEqual(len(intro.name), IntroScene.MAX_NAME)
        self.key(pygame.K_BACKSPACE)
        self.assertEqual(len(intro.name), IntroScene.MAX_NAME - 1)

    def test_route_is_locked_until_you_have_a_starter_then_choose_one(self):
        self.start_new_game()
        self.play_intro()
        ow = self.engine.current_scene
        state = self.engine.game_state

        # Gate north of town
        ow.teleport(Location("fernvale_town", 9, 1), Direction.UP)
        self.key(pygame.K_UP)
        self.frames(2, 0.2)
        self.assertEqual(ow.explorer.location.map_id, "fernvale_town")
        self.assertEqual(ow.mode, "DIALOGUE")
        while ow.mode == "DIALOGUE":
            self.frames()
            self.key(pygame.K_z)

        # Into the lab, face the fire starter's ball
        lab = self.engine.world.get("professor_lab")
        ball = next(e for e in lab.entities if isinstance(e, StarterBall) and e.species_id == 4)
        ow.teleport(Location("professor_lab", ball.x, ball.y + 1), Direction.UP)
        self.key(pygame.K_z)
        self.assertEqual(ow.mode, "CONFIRM_STARTER")
        self.frames()
        self.key(pygame.K_z)                       # finish typing the question
        ow.starter_menu.selected_index = 0         # YES
        self.key(pygame.K_z)
        self.frames()

        self.assertEqual([c.species_id for c in state.trainer.party.creatures], [4])
        self.assertEqual(state.rival_starter, 7)
        self.assertTrue(state.flags.has("has_starter"))
        while ow.mode == "DIALOGUE":
            self.frames()
            self.key(pygame.K_z)

        # The professor now hands over balls, once
        balls_before = state.trainer.get_item("poke_ball").quantity if state.trainer.has_item("poke_ball") else 0
        prof = next(e for e in lab.entities if isinstance(e, Professor))
        ow.teleport(Location("professor_lab", prof.x - 1, prof.y), Direction.RIGHT)
        self.key(pygame.K_z)
        self.assertGreater(state.trainer.get_item("poke_ball").quantity, balls_before)
        self.assertEqual(components.overflow_log(), [])

        # And now the gate opens
        while ow.mode == "DIALOGUE":
            self.frames()
            self.key(pygame.K_z)
        ow.teleport(Location("fernvale_town", 9, 1), Direction.UP)
        self.key(pygame.K_UP)
        self.frames(3, 0.2)
        self.assertEqual(ow.explorer.location.map_id, "route_1")

    def test_saying_no_keeps_the_ball(self):
        self.start_new_game()
        self.play_intro()
        ow = self.engine.current_scene
        lab = self.engine.world.get("professor_lab")
        ball = next(e for e in lab.entities if isinstance(e, StarterBall))
        ow.teleport(Location("professor_lab", ball.x, ball.y + 1), Direction.UP)
        self.key(pygame.K_z)
        self.frames()
        self.key(pygame.K_z)
        ow.starter_menu.selected_index = 1         # NO
        self.key(pygame.K_z)
        self.assertEqual(self.engine.game_state.trainer.party.size, 0)
        self.assertEqual(ow.mode, "WALK")


if __name__ == "__main__":
    unittest.main()
