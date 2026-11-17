"""Phase 6: trainer battles, the rival, the gym leader, badges and smarter opponents."""
import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model.badges import BadgeCase
from src.model.battle import BattleState, GymBattle, TrainerBattle, WildBattle
from src.model.battle_ai import BattleAI, SmartAI
from src.model.direction import Direction
from src.model.entities import GymLeader, NPC, RivalTrainer, TrainerNPC
from src.model.events import EventType
from src.model.game_state import GameState
from src.model.trainer import Party, Trainer
from src.model.world import Explorer, Location, World, WorldMap
from src.ui import components
from src.ui.battle_scene import BattleScene
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene


class _Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()

    def setUp(self):
        random.seed(5)

    def state_with(self, *creatures, money=1000):
        return GameState(Trainer("ALEX", Party(list(creatures)), money=money))

    def leo(self, **overrides):
        data = {"kind": "trainer", "id": "test_leo", "x": 5, "y": 1, "name": "LEO", "title": "YOUNGSTER",
                "facing": "down", "sight": 3, "party": [[19, 3], [16, 3]], "prize": 120,
                "lines": ["Let's battle!"], "defeat_lines": ["I lost!"], "after_lines": ["Good game."]}
        data.update(overrides)
        return TrainerNPC.from_data(data)

    def build(self, npc, state):
        return npc.build_battle(state, self.chart, self.loader.get_creature, self.loader.get_move)

    def win(self, battle, limit=40):
        for _ in range(limit):
            if not battle.is_active:
                return
            battle.player_creature.heal(999)
            battle.execute_move(0)
        self.fail("battle did not finish")


class TestTrainerBattles(_Model):
    def test_hierarchy(self):
        self.assertTrue(issubclass(GymBattle, TrainerBattle))
        self.assertTrue(issubclass(SmartAI, BattleAI))
        self.assertTrue(issubclass(GymLeader, TrainerNPC))
        self.assertTrue(issubclass(RivalTrainer, TrainerNPC))
        self.assertTrue(issubclass(TrainerNPC, NPC))

    def test_no_running_or_catching(self):
        state = self.state_with(self.loader.get_creature(4, 30))
        state.trainer.add_item(self.loader.get_item("poke_ball", 3), 3)
        battle = self.build(self.leo(), state)
        self.assertIsInstance(battle, TrainerBattle)
        self.assertFalse(battle.can_flee)
        self.assertEqual(battle.attempt_run()[0].event_type, EventType.INVALID_ACTION)
        self.assertEqual(battle.use_item("poke_ball")[0].event_type, EventType.INVALID_ACTION)
        self.assertEqual(state.trainer.get_item("poke_ball").quantity, 3, "ball not wasted")
        self.assertIn("YOUNGSTER LEO", battle.intro_message)

    def test_sends_out_next_creature_then_pays_prize_and_remembers_defeat(self):
        mine = self.loader.get_creature(6, 50)
        state = self.state_with(mine, money=1000)
        battle = self.build(self.leo(), state)
        first = battle.opponent

        events = battle.execute_move(0)
        kinds = [e.event_type for e in events]
        self.assertIn(EventType.OPPONENT_SENT, kinds)
        self.assertIsNot(battle.opponent, first)
        self.assertTrue(battle.is_active)

        self.win(battle)
        self.assertEqual(battle.state, BattleState.WON)
        self.assertEqual(state.trainer.money, 1120)
        self.assertTrue(state.flags.has("defeated_test_leo"))

    def test_trainer_battles_give_more_xp_than_wild(self):
        wild_mine = self.loader.get_creature(6, 50)
        wild = WildBattle(Trainer("A", Party([wild_mine])), self.loader.get_creature(19, 3), self.chart)
        xp_before = wild_mine.xp
        self.win(wild)
        wild_gain = wild_mine.xp - xp_before

        mine = self.loader.get_creature(6, 50)
        battle = self.build(self.leo(party=[[19, 3]]), self.state_with(mine))
        xp_before = mine.xp
        self.win(battle)
        self.assertGreater(mine.xp - xp_before, wild_gain)

    def test_gym_battle_awards_badge(self):
        leader = GymLeader.from_data({
            "kind": "gym_leader", "id": "test_gym", "x": 5, "y": 1, "name": "WREN", "title": "LEADER",
            "party": [[16, 3]], "prize": 500, "badge": "GALE BADGE", "lines": ["Hi"]})
        state = self.state_with(self.loader.get_creature(6, 50))
        battle = self.build(leader, state)
        self.assertIsInstance(battle, GymBattle)
        self.win(battle)
        self.assertTrue(state.badge_case.has("GALE BADGE"))
        self.assertEqual(state.badges, 1)

    def test_rival_team_uses_the_starter_they_picked(self):
        rival = RivalTrainer.from_data({
            "kind": "rival", "id": "rival_1", "x": 1, "y": 1, "name": "JUNO", "title": "RIVAL",
            "starter_level": 6, "party": [[16, 4]], "lines": ["Battle!"]})
        state = self.state_with(self.loader.get_creature(4, 10))
        state.rival_starter = 7
        battle = self.build(rival, state)
        self.assertEqual(battle.opponent.species_id, 7)
        self.assertEqual(battle.opponent.level, 6)


class TestSmartAI(_Model):
    def test_picks_the_super_effective_move(self):
        user = self.loader.get_creature(4, 20)          # Charmander: Scratch, Growl, Ember, Bite
        target = self.loader.get_creature(1, 20)        # Bulbasaur: Grass
        move = SmartAI(self.chart).choose_move(user, target)
        self.assertEqual(move.id, "ember")


class TestBadges(_Model):
    def test_badge_case(self):
        case = BadgeCase()
        self.assertTrue(case.add("GALE BADGE"))
        self.assertFalse(case.add("GALE BADGE"))
        self.assertEqual(case.count, 1)
        self.assertEqual(BadgeCase.from_list(case.to_list()).names, ("GALE BADGE",))

    def test_badges_saved(self):
        state = self.state_with(self.loader.get_creature(4))
        state.badge_case.add("GALE BADGE")
        loaded = GameState.from_dict(state.to_dict(), self.loader)
        self.assertTrue(loaded.badge_case.has("GALE BADGE"))


class TestLineOfSight(_Model):
    def setUp(self):
        super().setUp()
        self.trainer_npc = self.leo()
        m = WorldMap("m", "M", [["path"] * 9 for _ in range(9)], entities=[self.trainer_npc])
        m2 = WorldMap("m2", "M2", [["path"] * 9 for _ in range(9)])
        self.world = World([m, m2])
        self.state = self.state_with(self.loader.get_creature(4))

    def spotter(self, loc):
        return Explorer(self.world, loc, Direction.UP, flags=self.state.flags).spotted_by(self.state)

    def test_spots_player_in_range_in_front(self):
        self.assertIs(self.spotter(Location("m", 5, 4)), self.trainer_npc)

    def test_not_out_of_range_or_to_the_side(self):
        self.assertIsNone(self.spotter(Location("m", 5, 5)))
        self.assertIsNone(self.spotter(Location("m", 6, 3)))

    def test_not_after_defeat(self):
        self.state.flags.set("defeated_test_leo")
        self.assertIsNone(self.spotter(Location("m", 5, 3)))

    def test_interact_starts_battle_until_defeated(self):
        self.assertEqual(self.trainer_npc.interact(self.state, Direction.UP).effect, "start_battle")
        self.state.flags.set("defeated_test_leo")
        result = self.trainer_npc.interact(self.state, Direction.UP)
        self.assertIsNone(result.effect)
        self.assertEqual(result.lines, ("Good game.",))


class TestShippedContent(_Model):
    def test_route_trainer_rival_and_gym_exist(self):
        world = self.loader.load_world()
        route = world.get("route_1")
        self.assertTrue(any(type(e) is TrainerNPC for e in route.entities))
        self.assertTrue(any(isinstance(e, RivalTrainer) for e in route.entities))
        gym = world.get("brookhaven_gym")
        leaders = [e for e in gym.entities if isinstance(e, GymLeader)]
        self.assertEqual(len(leaders), 1)
        self.assertTrue(leaders[0].badge)
        city = world.get("brookhaven_city")
        self.assertTrue(any(w.target.map_id == "brookhaven_gym" for w in city.warps))


class TestTrainerUI(unittest.TestCase):
    def setUp(self):
        pygame.init()
        random.seed(3)
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        party = self.engine.game_state.trainer.party
        strong = self.engine.data_loader.get_creature(6, 60)
        party.add(strong)
        party.swap(0, 1)
        self.ow = OverworldScene(self.engine, rng=random.Random(0))
        self.ow.rng.random = lambda: 0.99      # no wild encounters
        self.engine.push_scene(self.ow)
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k):
        self.engine.current_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    def frames(self, n=1, dt=1.0):
        for _ in range(n):
            scene = self.engine.current_scene
            scene.update(dt)
            scene.draw(self.engine.native_surface)

    def fight_to_the_end(self, battle_scene):
        for _ in range(300):
            if self.engine.current_scene is not battle_scene:
                return
            if battle_scene.sub_state == "ACTION_SELECT":
                battle_scene.action_menu.selected_index = 0
                self.key(pygame.K_z)
                self.key(pygame.K_z)
            elif battle_scene.sub_state == "LEARN_SELECT":
                self.key(pygame.K_x)
            else:
                self.key(pygame.K_z)
            self.frames(1, 0.5)
        self.fail("battle never ended")

    def wait_for_battle(self):
        """Let the battle transition play, then return the battle scene."""
        for _ in range(30):
            if isinstance(self.engine.current_scene, BattleScene):
                break
            self.frames(1, 0.1)
        return self.engine.current_scene

    def finish_dialogue(self):
        for _ in range(30):
            if self.ow.mode != "DIALOGUE":
                return
            self.frames(1, 1.0)
            self.key(pygame.K_z)

    def test_route_trainer_spots_you_battles_and_pays(self):
        route = self.engine.world.get("route_1")
        npc = next(e for e in route.entities if type(e) is TrainerNPC)
        # stand just outside the trainer's sight, then step into it
        d = npc.facing
        far = Location("route_1", npc.x + d.dx * (npc.sight + 1), npc.y + d.dy * (npc.sight + 1))
        self.ow.teleport(far, d.opposite)
        money = self.engine.game_state.trainer.money
        self.key({Direction.UP: pygame.K_DOWN, Direction.DOWN: pygame.K_UP,
                  Direction.LEFT: pygame.K_RIGHT, Direction.RIGHT: pygame.K_LEFT}[d])
        self.frames(1, 0.3)                        # finish the step
        self.assertEqual(self.ow.mode, "SPOTTED", "trainer should spot the player")
        self.frames(3, 0.3)                        # the "!" pause
        self.assertEqual(self.ow.mode, "DIALOGUE")
        self.finish_dialogue()
        battle_scene = self.wait_for_battle()
        self.assertIsInstance(battle_scene, BattleScene)
        self.assertIsInstance(battle_scene.battle, TrainerBattle)

        self.fight_to_the_end(battle_scene)
        self.assertIs(self.engine.current_scene, self.ow)
        self.assertGreater(self.engine.game_state.trainer.money, money)
        self.assertTrue(self.engine.game_state.flags.has(f"defeated_{npc.trainer_id}"))
        self.assertEqual(self.ow.mode, "DIALOGUE", "trainer says their defeat lines")
        self.assertEqual(components.overflow_log(), [])

    def test_gym_leader_gives_badge(self):
        gym = self.engine.world.get("brookhaven_gym")
        leader = next(e for e in gym.entities if isinstance(e, GymLeader))
        for e in gym.entities:
            if isinstance(e, TrainerNPC) and e is not leader:
                self.engine.game_state.flags.set(f"defeated_{e.trainer_id}")
        self.ow.teleport(Location("brookhaven_gym", leader.x, leader.y + 1), Direction.UP)
        self.key(pygame.K_z)
        self.finish_dialogue()
        battle_scene = self.wait_for_battle()
        self.assertIsInstance(battle_scene.battle, GymBattle)
        self.fight_to_the_end(battle_scene)
        self.assertTrue(self.engine.game_state.badge_case.has(leader.badge))


if __name__ == "__main__":
    unittest.main()
