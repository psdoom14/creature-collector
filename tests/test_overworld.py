"""Phase 4: the overworld screen driven by real key presses."""
import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.model.direction import Direction
from src.model.world import Location
from src.ui import components
from src.ui.battle_scene import BattleScene
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene


class _AlwaysEncounter(random.Random):
    def random(self):
        return 0.0


class _NeverEncounter(random.Random):
    def random(self):
        return 0.99


class TestOverworld(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.ow = OverworldScene(self.engine, rng=_NeverEncounter())
        self.engine.push_scene(self.ow)
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k, scene=None):
        (scene or self.engine.current_scene).handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    def frames(self, n=6, dt=0.1):
        for _ in range(n):
            scene = self.engine.current_scene
            scene.update(dt)
            scene.draw(self.engine.native_surface)

    def walk(self, direction_key, steps):
        """Tap the key ``steps`` times (press and release), letting each step finish."""
        for _ in range(steps):
            self.key(direction_key)
            self.ow.handle_event(pygame.event.Event(pygame.KEYUP, key=direction_key))
            self.frames(5)

    def test_holding_a_direction_keeps_walking(self):
        self.ow.teleport(Location("fernvale_town", 9, 9), Direction.UP)
        self.key(pygame.K_UP)
        self.frames(10)                            # 1 second held
        self.ow.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP))
        self.frames(3)
        self.assertLessEqual(self.ow.explorer.location.y, 5)

    def test_starts_at_the_world_start(self):
        self.assertEqual(self.ow.explorer.location, self.engine.data_loader.start_location())
        self.assertEqual(self.engine.game_state.current_route, "Fernvale Town")

    def test_walk_north_out_of_town_onto_route_1(self):
        self.ow.teleport(Location("fernvale_town", 9, 2), Direction.UP)
        self.walk(pygame.K_UP, 2)
        self.assertEqual(self.ow.explorer.location.map_id, "route_1")
        self.assertEqual(self.engine.game_state.current_route, "Route 1")
        self.assertTrue(self.ow.location_banner_visible)

    def test_enter_healing_center_and_get_healed(self):
        trainer = self.engine.game_state.trainer
        trainer.party.creatures[0].take_damage(999)

        self.ow.teleport(Location("brookhaven_city", 5, 6), Direction.UP)
        self.walk(pygame.K_UP, 1)                  # through the door
        self.assertEqual(self.ow.explorer.location, Location("healing_center", 5, 6))

        self.walk(pygame.K_UP, 3)                  # up to the counter
        self.assertEqual(self.ow.explorer.location, Location("healing_center", 5, 3))
        self.key(pygame.K_z)                       # talk across the counter
        self.assertEqual(self.ow.mode, "DIALOGUE")
        self.assertFalse(trainer.party.creatures[0].is_fainted)
        presses = 0
        while self.ow.mode == "DIALOGUE" and presses < 12:
            self.frames(1, 1.0)
            self.key(pygame.K_z)
            presses += 1
        self.assertEqual(self.ow.mode, "WALK", "dialogue should end within a few presses")
        self.assertEqual(self.engine.game_state.respawn_location, Location("healing_center", 5, 3))
        self.assertEqual(components.overflow_log(), [])

        self.walk(pygame.K_DOWN, 4)                # back out of the door
        self.assertEqual(self.ow.explorer.location, Location("brookhaven_city", 5, 6))

    def test_blackout_respawns_at_last_healing_center(self):
        self.engine.game_state.respawn_location = Location("healing_center", 5, 3)
        self.ow.teleport(Location("route_1", 7, 10), Direction.DOWN)
        self.ow.respawn_after_blackout(100)
        self.assertEqual(self.ow.explorer.location, Location("healing_center", 5, 3))
        self.assertEqual(self.engine.game_state.current_route, "Healing Center")

    def test_tall_grass_starts_a_battle(self):
        self.ow.rng = _AlwaysEncounter()
        self.ow.teleport(Location("route_1", 7, 5), Direction.UP)
        world_map = self.ow.explorer.current_map
        grass = next((x, y) for y in range(world_map.height) for x in range(world_map.width)
                     if world_map.tile_at(x, y).encounters
                     and world_map.is_passable(x - 1, y) and not world_map.tile_at(x - 1, y).encounters)
        self.ow.teleport(Location("route_1", grass[0] - 1, grass[1]), Direction.RIGHT)
        self.walk(pygame.K_RIGHT, 1)
        for _ in range(30):          # the battle transition plays first
            if isinstance(self.engine.current_scene, BattleScene):
                break
            self.frames(1, 0.1)
        self.assertIsInstance(self.engine.current_scene, BattleScene)

    def test_menu_opens_with_enter_and_talk_uses_z(self):
        self.key(pygame.K_RETURN)
        self.assertEqual(self.ow.mode, "MENU")
        self.key(pygame.K_x)
        self.assertEqual(self.ow.mode, "WALK")

    def test_camera_keeps_player_on_screen_on_big_maps(self):
        self.ow.teleport(Location("route_1", 8, 22), Direction.UP)
        px, py = self.ow._player_pixel_pos()
        cx, cy = self.ow.renderer.camera_offset(px, py)
        self.assertTrue(0 <= px - cx < 240 and 0 <= py - cy < 160)
        self.assertLessEqual(cy, self.ow.renderer.pixel_h - 160)


if __name__ == "__main__":
    unittest.main()
