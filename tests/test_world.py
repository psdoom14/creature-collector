"""Phase 4: world model (maps, warps, entities) and the shipped map data."""
import random
import unittest
from collections import deque

from src.data_loader import DataLoader
from src.model.entities import Character, Healer, Interactable, NPC, Sign
from src.model.game_state import GameState
from src.model.trainer import Party, Trainer
from src.model.world import Direction, Explorer, Location, World, WorldMap

TINY_MAP = {
    "id": "tiny",
    "name": "Tiny Town",
    "legend": {"T": "tree", ",": "path", '"': "tall_grass", "K": "counter",
               "R": "house_roof", "W": "house_wall", "D": "house_door"},
    "rows": [
        "TTTTT",
        "T,,,T",
        'T,"",',
        "T,K,T",
        "T,,,T",
        "TWDWT",
    ],
    "encounters": "Route 1",
    "encounter_rate": 0.5,
    "warps": [
        {"x": 4, "y": 2, "to": "other", "tx": 1, "ty": 1, "facing": "right"},
    ],
    "entities": [
        {"kind": "sign", "x": 3, "y": 4, "lines": ["Welcome to Tiny Town!"]},
        {"kind": "npc", "x": 1, "y": 4, "name": "KID", "facing": "up", "lines": ["Hi!"]},
        {"kind": "healer", "x": 2, "y": 2, "name": "NURSE", "facing": "down", "lines": ["Hello!"]},
    ],
}
OTHER_MAP = {
    "id": "other", "name": "Other", "legend": {".": "grass", "T": "tree"},
    "rows": ["TTT", "T.T", "TTT"], "warps": [], "entities": [],
}


def tiny_world() -> World:
    return World([WorldMap.from_dict(TINY_MAP), WorldMap.from_dict(OTHER_MAP)])


class TestBasics(unittest.TestCase):
    def test_direction_and_location(self):
        self.assertEqual(Direction.UP.opposite, Direction.DOWN)
        self.assertEqual(Location("m", 2, 2).moved(Direction.LEFT), Location("m", 1, 2))
        self.assertIs(Direction.from_name("right"), Direction.RIGHT)

    def test_bad_map_data_is_rejected(self):
        bad_width = dict(TINY_MAP, rows=["TTT", "TT"])
        with self.assertRaises(ValueError):
            WorldMap.from_dict(bad_width)
        bad_char = dict(TINY_MAP, rows=["TTTTT", "T?,,T", 'T,"",', "T,K,T", "T,,,T", "TWDWT"])
        with self.assertRaises(ValueError):
            WorldMap.from_dict(bad_char)


class TestExplorer(unittest.TestCase):
    def setUp(self):
        self.world = tiny_world()
        self.ex = Explorer(self.world, Location("tiny", 1, 1), Direction.DOWN)

    def test_walks_on_path_and_is_blocked_by_trees(self):
        self.assertFalse(self.ex.step(Direction.UP).moved)
        self.assertEqual(self.ex.facing, Direction.UP, "turning still happens when blocked")
        self.assertTrue(self.ex.step(Direction.RIGHT).moved)
        self.assertEqual(self.ex.location, Location("tiny", 2, 1))

    def test_entities_and_counters_block(self):
        self.ex.teleport(Location("tiny", 1, 3), Direction.DOWN)
        self.assertFalse(self.ex.step(Direction.DOWN).moved, "NPC stands there")
        self.assertFalse(self.ex.step(Direction.RIGHT).moved, "counter")

    def test_doors_without_warps_are_walls(self):
        self.ex.teleport(Location("tiny", 2, 4), Direction.DOWN)
        self.assertFalse(self.ex.step(Direction.DOWN).moved)

    def test_stepping_on_a_warp_changes_map(self):
        self.ex.teleport(Location("tiny", 3, 2), Direction.RIGHT)
        result = self.ex.step(Direction.RIGHT)
        self.assertTrue(result.warped)
        self.assertEqual(self.ex.location, Location("other", 1, 1))
        self.assertEqual(self.ex.facing, Direction.RIGHT)
        self.assertEqual(self.ex.current_map.name, "Other")

    def test_encounters_only_in_tall_grass(self):
        rng = random.Random()
        rng.random = lambda: 0.0
        self.ex.teleport(Location("tiny", 1, 2), Direction.RIGHT)
        self.assertIsNone(self.ex.roll_encounter(rng), "path tile: no encounters")
        self.ex.teleport(Location("tiny", 3, 2), Direction.LEFT)
        self.assertEqual(self.ex.roll_encounter(rng), "Route 1")
        rng.random = lambda: 0.99
        self.assertIsNone(self.ex.roll_encounter(rng))


class TestEntities(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()
        self.world = tiny_world()
        self.ex = Explorer(self.world, Location("tiny", 1, 1), Direction.DOWN)
        self.trainer = Trainer("A", Party([self.loader.get_creature(4, 5)]))
        self.state = GameState(self.trainer)

    def test_hierarchy(self):
        self.assertTrue(issubclass(Healer, NPC))
        self.assertTrue(issubclass(NPC, Character))
        self.assertTrue(issubclass(Character, Interactable))
        self.assertTrue(issubclass(Sign, Interactable))
        with self.assertRaises(TypeError):
            Interactable(0, 0)  # type: ignore[abstract]

    def test_sign(self):
        self.ex.teleport(Location("tiny", 3, 3), Direction.DOWN)
        result = self.ex.interact(self.state)
        self.assertEqual(result.lines, ("Welcome to Tiny Town!",))

    def test_npc_turns_to_face_the_player(self):
        self.ex.teleport(Location("tiny", 2, 4), Direction.LEFT)
        npc = self.ex.facing_target()
        self.assertIsInstance(npc, NPC)
        self.ex.interact(self.state)
        self.assertEqual(npc.facing, Direction.RIGHT)

    def test_talking_to_nothing(self):
        self.ex.teleport(Location("tiny", 1, 1), Direction.RIGHT)
        self.assertIsNone(self.ex.interact(self.state))

    def test_healer_heals_across_the_counter(self):
        mon = self.trainer.party.creatures[0]
        mon.take_damage(999)
        self.ex.teleport(Location("tiny", 2, 4), Direction.UP)
        # (2,3) is the counter; the healer stands behind it at (2,2)
        self.assertIsInstance(self.ex.facing_target(), Healer)
        result = self.ex.interact(self.state)
        self.assertFalse(mon.is_fainted)
        self.assertEqual(result.effect, "healed")
        self.assertGreater(len(result.lines), 1)


class TestShippedWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.world = cls.loader.load_world()
        cls.start = cls.loader.start_location()

    def passable_neighbours(self, loc):
        m = self.world.get(loc.map_id)
        for d in Direction:
            nxt = loc.moved(d)
            if m.is_passable(nxt.x, nxt.y):
                warp = m.warp_at(nxt.x, nxt.y)
                yield warp.target if warp else nxt

    def reachable(self):
        seen = {self.start}
        queue = deque([self.start])
        while queue:
            loc = queue.popleft()
            for nxt in self.passable_neighbours(loc):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def test_has_two_towns_a_route_and_a_healing_center(self):
        ids = set(self.world.map_ids)
        self.assertGreaterEqual(len(ids), 4)
        self.assertTrue(any(m.encounter_table for m in self.world.maps))
        self.assertTrue(any(isinstance(e, Healer) for m in self.world.maps for e in m.entities))

    def test_start_is_passable(self):
        m = self.world.get(self.start.map_id)
        self.assertTrue(m.is_passable(self.start.x, self.start.y))

    def test_every_warp_lands_on_a_safe_passable_tile(self):
        for m in self.world.maps:
            for warp in m.warps:
                with self.subTest(map=m.id, warp=(warp.x, warp.y)):
                    target_map = self.world.get(warp.target.map_id)
                    self.assertTrue(target_map.is_passable(warp.target.x, warp.target.y))
                    self.assertIsNone(target_map.warp_at(warp.target.x, warp.target.y),
                                      "landing on another warp would bounce the player")

    def test_every_map_and_the_healer_are_reachable_from_the_start(self):
        reached = self.reachable()
        self.assertEqual({loc.map_id for loc in reached}, set(self.world.map_ids))

        healer_spots = []
        for m in self.world.maps:
            for e in m.entities:
                if isinstance(e, Healer):
                    healer_spots.append((m.id, e))
        for map_id, healer in healer_spots:
            ok = False
            for loc in reached:
                if loc.map_id != map_id:
                    continue
                for d in Direction:
                    ex = Explorer(self.world, loc, d)
                    if ex.facing_target() is healer:
                        ok = True
            self.assertTrue(ok, f"no tile can talk to the healer in {map_id}")

    def test_encounter_tables_exist(self):
        for m in self.world.maps:
            if m.encounter_table:
                with self.subTest(map=m.id):
                    self.assertIsNotNone(self.loader.get_wild_encounter(m.encounter_table))


class TestSavedLocation(unittest.TestCase):
    def test_location_and_respawn_round_trip(self):
        loader = DataLoader()
        gs = GameState(Trainer("A", Party([loader.get_creature(4)])))
        gs.location = Location("route_1", 3, 4)
        gs.facing = Direction.LEFT
        gs.respawn_location = Location("healing_center", 5, 3)
        loaded = GameState.from_dict(gs.to_dict(), loader)
        self.assertEqual(loaded.location, Location("route_1", 3, 4))
        self.assertEqual(loaded.facing, Direction.LEFT)
        self.assertEqual(loaded.respawn_location, Location("healing_center", 5, 3))


if __name__ == "__main__":
    unittest.main()
