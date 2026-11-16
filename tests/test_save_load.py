"""Tests for SaveManager and GameState serialization."""
import unittest
import tempfile
from pathlib import Path

from src.data_loader import DataLoader
from src.model.trainer import Trainer, Party
from src.model.pokedex import Pokedex
from src.model.game_state import GameState
from src.save_manager import SaveManager


class TestSaveLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()

    def test_save_and_load_roundtrip(self):
        starter = self.loader.get_creature(4, level=7)  # Charmander
        party = Party([starter])
        trainer = Trainer("Ash", party, money=5000)

        potion = self.loader.get_item("potion", quantity=3)
        trainer.add_item(potion, 3)

        pokedex = Pokedex()
        pokedex.register_caught(4)
        pokedex.register_seen(16)

        original_state = GameState(
            trainer=trainer,
            pokedex=pokedex,
            current_route="Route 2",
            play_time=120.5,
            badges=1,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Save
            success = SaveManager.save_game(original_state, tmp_path)
            self.assertTrue(success)

            # Load
            loaded_state = SaveManager.load_game(tmp_path, self.loader)
            self.assertEqual(loaded_state.trainer.name, "Ash")
            self.assertEqual(loaded_state.trainer.money, 5000)
            self.assertEqual(loaded_state.current_route, "Route 2")
            self.assertEqual(loaded_state.badges, 1)

            # Check party
            self.assertEqual(loaded_state.trainer.party.size, 1)
            loaded_creature = loaded_state.trainer.party.creatures[0]
            self.assertEqual(loaded_creature.name, "Charmander")
            self.assertEqual(loaded_creature.level, 7)

            # Check inventory
            self.assertTrue(loaded_state.trainer.has_item("potion"))
            self.assertEqual(loaded_state.trainer.get_item("potion").quantity, 3)

            # Check pokedex
            self.assertTrue(loaded_state.pokedex.is_caught(4))
            self.assertTrue(loaded_state.pokedex.is_seen(16))
            self.assertFalse(loaded_state.pokedex.is_caught(16))

        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
