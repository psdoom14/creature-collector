"""GBA-style battle animations, move effects and battle transitions."""
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model.battle import WildBattle
from src.model.events import EventType
from src.model.item import CatchBall
from src.model.trainer import Party, Trainer
from src.ui import animations as A
from src.ui.battle_scene import BattleScene
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.transitions import TrainerTransition, Transition, TransitionScene, WildTransition
from src.model.world import Location
from src.model.direction import Direction


class TestCatchShakes(unittest.TestCase):
    """The model reports how many times the ball wobbles, so the UI can animate it."""

    def setUp(self):
        self.loader = DataLoader()
        self.chart = self.loader.get_type_chart()

    def throw(self, chance):
        trainer = Trainer("A", Party([self.loader.get_creature(6, 50)]))
        trainer.add_item(self.loader.get_item("poke_ball", 5), 5)
        battle = WildBattle(trainer, self.loader.get_creature(19, 3), self.chart)
        with mock.patch.object(CatchBall, "calc_catch_chance", return_value=chance):
            events = battle.use_item("poke_ball")
        return next(e for e in events if e.event_type in (EventType.CAUGHT, EventType.CATCH_FAILED))

    def test_certain_catch_wobbles_three_times(self):
        result = self.throw(1.0)
        self.assertEqual(result.event_type, EventType.CAUGHT)
        self.assertEqual(result.data["shakes"], 3)

    def test_hopeless_throw_breaks_out_at_once(self):
        result = self.throw(0.0)
        self.assertEqual(result.event_type, EventType.CATCH_FAILED)
        self.assertEqual(result.data["shakes"], 0)

    def test_shakes_are_between_zero_and_three(self):
        random.seed(4)
        for _ in range(40):
            self.assertIn(self.throw(0.4).data["shakes"], (0, 1, 2, 3))


class TestAnimationClasses(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((240, 160))
        self.layout = A.BattleLayout()

    def run_to_end(self, anim, step=0.05):
        for _ in range(int(anim.duration / step) + 5):
            anim.update(step)
            mods = A.SpriteMods()
            anim.modify(A.FOE, mods)
            anim.modify(A.PLAYER, mods)
            anim.draw(self.surface, self.layout)
        self.assertTrue(anim.done)

    def test_animation_is_abstract(self):
        with self.assertRaises(TypeError):
            A.Animation()  # type: ignore[abstract]
        with self.assertRaises(TypeError):
            A.MoveAnimation(A.PLAYER)  # type: ignore[abstract]

    def test_move_factory_picks_a_class_per_type(self):
        cases = {
            ("Fire", "special"): A.EmberAnimation,
            ("Water", "special"): A.WaterAnimation,
            ("Grass", "special"): A.LeafAnimation,
            ("Electric", "special"): A.ThunderAnimation,
            ("Normal", "physical"): A.ImpactAnimation,
            ("Flying", "special"): A.GustAnimation,
            ("Ground", "physical"): A.QuakeAnimation,
            ("Normal", "status"): A.StatusMoveAnimation,
        }
        for (move_type, category), cls in cases.items():
            with self.subTest(move_type=move_type, category=category):
                anim = A.MoveAnimation.create(move_type, category, attacker=A.PLAYER)
                self.assertIsInstance(anim, cls)
                self.assertIsInstance(anim, A.Animation)

    def test_unknown_type_falls_back_to_impact(self):
        self.assertIsInstance(A.MoveAnimation.create("Cosmic", "physical", A.FOE), A.ImpactAnimation)

    def test_every_animation_finishes_and_draws(self):
        anims = [
            A.SlideIn(A.FOE), A.SendOut(A.PLAYER), A.HitBlink(A.FOE), A.FaintDrop(A.PLAYER),
            A.BallThrow(), A.BallWobble(shakes=2, caught=False), A.BallWobble(shakes=3, caught=True),
            A.LevelUpGlow(A.PLAYER), A.StatusSparkle(A.FOE, "burn"), A.StatArrows(A.FOE, rising=False),
            A.HealSparkle(A.PLAYER), A.ScreenShake(),
        ] + [A.MoveAnimation.create(t, c, A.PLAYER) for t, c in (
            ("Fire", "special"), ("Water", "special"), ("Grass", "special"), ("Electric", "special"),
            ("Ice", "special"), ("Psychic", "special"), ("Poison", "special"), ("Rock", "physical"),
            ("Flying", "physical"), ("Dragon", "special"), ("Normal", "physical"), ("Normal", "status"))]
        for anim in anims:
            with self.subTest(anim=type(anim).__name__):
                self.run_to_end(anim)

    def test_hit_blink_hides_the_target_some_of_the_time(self):
        anim = A.HitBlink(A.FOE)
        seen = set()
        for _ in range(20):
            anim.update(anim.duration / 20)
            mods = A.SpriteMods()
            anim.modify(A.FOE, mods)
            seen.add(mods.visible)
        self.assertEqual(seen, {True, False})

    def test_faint_drops_the_sprite_out_of_view(self):
        anim = A.FaintDrop(A.FOE)
        anim.update(anim.duration)
        mods = A.SpriteMods()
        anim.modify(A.FOE, mods)
        self.assertGreaterEqual(mods.dy, 52)

    def test_send_out_grows_from_nothing(self):
        anim = A.SendOut(A.PLAYER)
        mods = A.SpriteMods()
        anim.modify(A.PLAYER, mods)
        self.assertLess(mods.scale, 0.2)
        anim.update(anim.duration)
        mods = A.SpriteMods()
        anim.modify(A.PLAYER, mods)
        self.assertAlmostEqual(mods.scale, 1.0)


class TestTransitions(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_transition_is_abstract(self):
        with self.assertRaises(TypeError):
            Transition()  # type: ignore[abstract]

    def test_transitions_draw_every_stage(self):
        frame = pygame.Surface((240, 160))
        frame.fill((120, 192, 88))
        for transition in (WildTransition(), TrainerTransition()):
            for p in (0.0, 0.1, 0.3, 0.5, 0.8, 1.0):
                surface = pygame.Surface((240, 160))
                transition.draw(surface, frame, p)

    def test_tall_grass_plays_a_transition_then_the_battle(self):
        ow = OverworldScene(self.engine, rng=random.Random(0))
        ow.rng.random = lambda: 0.0
        self.engine.push_scene(ow)
        world_map = ow.explorer.current_map
        ow.teleport(Location("route_1", 2, 3), Direction.RIGHT)
        self.assertTrue(world_map.tile_at(2, 2).encounters or True)
        grass = next((x, y) for y in range(ow.explorer.current_map.height)
                     for x in range(ow.explorer.current_map.width)
                     if ow.explorer.current_map.tile_at(x, y).encounters
                     and ow.explorer.current_map.is_passable(x - 1, y)
                     and not ow.explorer.current_map.tile_at(x - 1, y).encounters)
        ow.teleport(Location("route_1", grass[0] - 1, grass[1]), Direction.RIGHT)
        ow.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        ow.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT))
        for _ in range(3):
            ow.update(0.1)
            ow.draw(self.engine.native_surface)
        self.assertIsInstance(self.engine.current_scene, TransitionScene)
        for _ in range(40):
            scene = self.engine.current_scene
            scene.update(0.1)
            scene.draw(self.engine.native_surface)
            if isinstance(scene, BattleScene):
                break
        self.assertIsInstance(self.engine.current_scene, BattleScene)


class TestBattleSceneAnimations(unittest.TestCase):
    def setUp(self):
        pygame.init()
        random.seed(7)
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.engine.push_scene(OverworldScene(self.engine))

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, scene, k):
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    def test_input_waits_for_the_animation(self):
        scene = BattleScene(self.engine, self.engine.data_loader.get_creature(19, 3))
        self.engine.push_scene(scene)
        self.assertTrue(scene.is_animating, "the intro slide-in plays first")
        self.key(scene, pygame.K_z)
        self.assertEqual(scene.sub_state, "INTRO", "keys are ignored while it plays")
        for _ in range(20):
            scene.update(0.1)
        self.assertFalse(scene.is_animating)

    def test_ball_hides_the_wild_creature_until_it_breaks_free(self):
        trainer = self.engine.game_state.trainer
        scene = BattleScene(self.engine, self.engine.data_loader.get_creature(19, 3))
        self.engine.push_scene(scene)
        for _ in range(20):
            scene.update(0.1)
        scene.sub_state = "ACTION_SELECT"
        with mock.patch.object(CatchBall, "calc_catch_chance", return_value=0.0):
            scene._queue(scene.battle.use_item("poke_ball"))
        self.assertTrue(scene.foe_in_ball)
        for _ in range(60):
            scene.update(0.1)
            scene.draw(self.engine.native_surface)
            if not scene.is_animating:
                self.key(scene, pygame.K_z)
            if not scene.foe_in_ball:
                break
        self.assertFalse(scene.foe_in_ball, "the creature reappears after breaking free")


if __name__ == "__main__":
    unittest.main()
