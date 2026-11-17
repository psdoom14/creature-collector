"""Regression tests for gameplay bugs found in the 2026-11-17 review (docs/PLAN.md, Part 1A).

Each test reproduces one bug. They were written to FAIL on the old code and
pass once the bug is fixed, so the fix can't silently regress later.
"""
import random
import unittest

from src.data_loader import DataLoader
from src.model.battle import Battle, BattleState
from src.model.trainer import Party, Trainer


class TestBugRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()

    def setUp(self):
        random.seed(1234)

    # B1 ---------------------------------------------------------------
    def test_b1_wild_creature_out_of_pp_uses_struggle_instead_of_crashing(self):
        player = self.loader.get_creature(4, level=5)   # Charmander
        wild = self.loader.get_creature(25, level=5)    # Pikachu
        for move in wild.moves:
            while move.use():
                pass

        battle = Battle(Trainer("A", Party([player])), wild, self.chart)
        events = battle.execute_move(0)  # used to raise NameError: MoveFactory

        messages = [e.message for e in events]
        self.assertIn(f"{wild.name} used Struggle!", messages)

    # B2 ---------------------------------------------------------------
    def test_b2_healing_center_revives_fainted_creatures(self):
        lead = self.loader.get_creature(4, level=10)
        backup = self.loader.get_creature(7, level=10)
        backup.take_damage(9999)
        party = Party([lead, backup])

        party.heal_all()

        self.assertFalse(backup.is_fainted)
        self.assertEqual(backup.current_hp, backup.max_hp)

    def test_b2_healing_center_restores_pp(self):
        lead = self.loader.get_creature(4, level=10)
        move = lead.moves[0]
        move.use()
        Party([lead]).heal_all()
        self.assertEqual(move.current_pp, move.max_pp)

    # B3 ---------------------------------------------------------------
    def test_b3_sleep_wears_off(self):
        player = self.loader.get_creature(4, level=5)
        wild = self.loader.get_creature(74, level=5)   # Geodude: resists Fire, survives a while
        self.assertTrue(wild.apply_status("sleep"))
        battle = Battle(Trainer("A", Party([player])), wild, self.chart)

        for _ in range(6):
            if not battle.is_active or wild.status_effect != "sleep":
                break
            player.heal(player.max_hp)
            wild.heal(wild.max_hp)
            battle.execute_move(0)

        self.assertNotEqual(wild.status_effect, "sleep", "creature stayed asleep for 6 turns")

    # B6 ---------------------------------------------------------------
    def test_b6_catch_with_full_party_goes_to_pc_box(self):
        party = Party([self.loader.get_creature(6, level=60) for _ in range(6)])
        trainer = Trainer("A", party)
        trainer.add_item(self.loader.get_item("ultra_ball", 50), 50)
        wild = self.loader.get_creature(19, level=2)   # Rattata, catch rate 255
        wild.take_damage(wild.max_hp - 1)

        battle = Battle(trainer, wild, self.chart)
        while battle.is_active:
            battle.attempt_catch("ultra_ball")

        self.assertEqual(battle.state, BattleState.CAUGHT)
        self.assertEqual(party.size, 6)
        self.assertIn(wild, trainer.pc.creatures)

    # B12 --------------------------------------------------------------
    def test_b12_status_immunities_respect_every_type(self):
        bulbasaur = self.loader.get_creature(1, level=5)   # Grass/Poison
        charmander = self.loader.get_creature(4, level=5)  # Fire
        pikachu = self.loader.get_creature(25, level=5)    # Electric

        self.assertFalse(bulbasaur.apply_status("poison"), "Poison types can't be poisoned")
        self.assertFalse(charmander.apply_status("burn"), "Fire types can't be burned")
        self.assertFalse(pikachu.apply_status("paralyze"), "Electric types can't be paralyzed")
        self.assertTrue(charmander.apply_status("poison"))


if __name__ == "__main__":
    unittest.main()
