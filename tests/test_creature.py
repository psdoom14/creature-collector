"""Tests for Creature model, leveling, and evolution."""
import unittest
from src.data_loader import DataLoader
from src.model.creature import FireCreature


class TestCreature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()

    def test_creature_initialization(self):
        charmander = self.loader.get_creature(4, level=5)
        self.assertIsInstance(charmander, FireCreature)
        self.assertEqual(charmander.name, "Charmander")
        self.assertEqual(charmander.level, 5)
        self.assertGreater(charmander.max_hp, 0)
        self.assertEqual(charmander.current_hp, charmander.max_hp)
        self.assertFalse(charmander.is_fainted)
        self.assertGreaterEqual(len(charmander.moves), 1)

    def test_damage_and_faint(self):
        squirtle = self.loader.get_creature(7, level=5)
        initial_hp = squirtle.current_hp
        loss = squirtle.take_damage(10)
        self.assertEqual(loss, 10)
        self.assertEqual(squirtle.current_hp, initial_hp - 10)
        self.assertFalse(squirtle.is_fainted)

        # Overkill damage
        squirtle.take_damage(9999)
        self.assertEqual(squirtle.current_hp, 0)
        self.assertTrue(squirtle.is_fainted)

    def test_healing_and_revive(self):
        bulbasaur = self.loader.get_creature(1, level=10)
        bulbasaur.take_damage(15)
        healed = bulbasaur.heal(10)
        self.assertEqual(healed, 10)

        # Faint then revive
        bulbasaur.take_damage(9999)
        self.assertTrue(bulbasaur.is_fainted)
        # Regular heal cannot revive
        self.assertEqual(bulbasaur.heal(20), 0)
        # Revive item effect
        revived = bulbasaur.revive(0.5)
        self.assertGreater(revived, 0)
        self.assertFalse(bulbasaur.is_fainted)

    def test_level_up_and_evolution_trigger(self):
        charmander = self.loader.get_creature(4, level=15)
        self.assertFalse(charmander.can_evolve())

        # Give sufficient XP to reach level 16
        # XP needed for level 16 is 16^3 = 4096
        xp_to_add = (16 ** 3) - charmander.xp
        res = charmander.gain_xp(xp_to_add)
        self.assertTrue(res["leveled_up"])
        self.assertEqual(charmander.level, 16)
        self.assertTrue(charmander.can_evolve())

        # Test evolution into Charmeleon (species 5)
        charmeleon_data = self.loader.get_species_data(5)
        evolved = charmander.evolve(charmeleon_data)
        self.assertEqual(evolved.name, "Charmeleon")
        self.assertEqual(evolved.level, 16)
        self.assertGreater(evolved.attack, charmander.attack)


if __name__ == "__main__":
    unittest.main()
