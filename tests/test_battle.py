"""Tests for Battle engine execution, catching, and fleeing."""
import unittest
from src.data_loader import DataLoader
from src.model.trainer import Trainer, Party
from src.model.battle import BattleState, WildBattle as Battle


class TestBattle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()

    def test_battle_player_turn(self):
        starter = self.loader.get_creature(4, level=10)  # Charmander
        wild = self.loader.get_creature(19, level=3)     # Rattata
        trainer = Trainer("Red", Party([starter]))

        battle = Battle(trainer, wild, self.chart)
        self.assertTrue(battle.is_active)

        events = battle.execute_move(0)
        self.assertGreaterEqual(len(events), 1)

    def test_battle_win_awards_xp(self):
        starter = self.loader.get_creature(6, level=50)  # High level Charizard
        wild = self.loader.get_creature(19, level=2)     # Low level Rattata
        trainer = Trainer("Red", Party([starter]))

        battle = Battle(trainer, wild, self.chart)
        events = battle.execute_move(0)

        # High level should faint wild in 1 hit
        self.assertEqual(battle.state, BattleState.WON)
        event_types = [e.event_type for e in events]
        self.assertIn("fainted", event_types)
        self.assertIn("xp_gained", event_types)
        self.assertIn("battle_won", event_types)

    def test_catch_mechanic(self):
        starter = self.loader.get_creature(4, level=10)
        wild = self.loader.get_creature(19, level=2)
        wild.take_damage(wild.max_hp - 1)  # 1 HP remaining

        trainer = Trainer("Red", Party([starter]))
        poke_ball = self.loader.get_item("poke_ball", quantity=5)
        trainer.add_item(poke_ball, 5)

        battle = Battle(trainer, wild, self.chart)
        events = battle.attempt_catch("poke_ball")

        event_types = [e.event_type for e in events]
        self.assertIn("ball_thrown", event_types)
        self.assertTrue("caught" in event_types or "catch_failed" in event_types)

    def test_flee_mechanic(self):
        # Fast starter vs slow wild creature
        starter = self.loader.get_creature(25, level=50) # Very fast Pikachu
        wild = self.loader.get_creature(74, level=2)     # Slow Geodude
        trainer = Trainer("Red", Party([starter]))

        battle = Battle(trainer, wild, self.chart)
        events = battle.attempt_run()
        event_types = [e.event_type for e in events]
        self.assertTrue("fled" in event_types or "flee_failed" in event_types)


if __name__ == "__main__":
    unittest.main()
