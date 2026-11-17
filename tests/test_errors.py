"""Exception handling: a custom exception hierarchy, safe saving, and damaged save files."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model.errors import (
    CorruptSaveError, GameDataError, GameError, RuleViolation, SaveError, SaveNotFoundError,
    SaveWriteError, UnknownIdError,
)
from src.model.game_state import GameState
from src.model.trainer import Party, Trainer
from src.model.world import WorldMap
from src.save_manager import SaveManager
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.title_scene import TitleScene


class TestHierarchy(unittest.TestCase):
    def test_every_game_error_shares_one_base(self):
        for cls in (GameDataError, UnknownIdError, RuleViolation, SaveError,
                    SaveNotFoundError, CorruptSaveError, SaveWriteError):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, GameError))

    def test_still_compatible_with_builtin_errors(self):
        self.assertTrue(issubclass(UnknownIdError, KeyError))
        self.assertTrue(issubclass(GameDataError, ValueError))
        self.assertTrue(issubclass(RuleViolation, ValueError))
        self.assertTrue(issubclass(SaveNotFoundError, FileNotFoundError))


class TestRaisedWhereExpected(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()

    def test_unknown_ids_in_data(self):
        for call in (lambda: self.loader.get_move("no_such_move"),
                     lambda: self.loader.get_item("no_such_item"),
                     lambda: self.loader.get_creature(9999)):
            with self.assertRaises(UnknownIdError):
                call()

    def test_broken_rules(self):
        with self.assertRaises(RuleViolation):
            Party([self.loader.get_creature(4) for _ in range(7)])
        with self.assertRaises(RuleViolation):
            self.loader.get_item("potion").add_stock(-1)
        with self.assertRaises(RuleViolation):
            Trainer("A").rename("   ")

    def test_bad_map_data(self):
        with self.assertRaises(GameDataError):
            WorldMap.from_dict({"id": "m", "name": "M", "legend": {".": "grass"}, "rows": ["..", "."]})
        with self.assertRaises(GameDataError):
            WorldMap.from_dict({"id": "m", "name": "M", "legend": {".": "lava"}, "rows": [".."]})


class TestSaving(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "save.json"
        self.state = GameState(Trainer("ALEX", Party([self.loader.get_creature(4, 7)]), money=500))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file(self):
        with self.assertRaises(SaveNotFoundError):
            SaveManager.load_game(self.path, self.loader)

    def test_not_json(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(CorruptSaveError) as ctx:
            SaveManager.load_game(self.path, self.loader)
        self.assertIsInstance(ctx.exception.__cause__, json.JSONDecodeError, "original error is kept")

    def test_unknown_species_is_reported_not_dropped(self):
        SaveManager.save_game(self.state, self.path)
        data = json.loads(self.path.read_text())
        data["trainer"]["party"][0]["species_id"] = 9999
        self.path.write_text(json.dumps(data))
        with self.assertRaises(CorruptSaveError):
            SaveManager.load_game(self.path, self.loader)

    def test_save_from_a_newer_version_is_rejected(self):
        SaveManager.save_game(self.state, self.path)
        data = json.loads(self.path.read_text())
        data["version"] = SaveManager.SAVE_VERSION + 1
        self.path.write_text(json.dumps(data))
        with self.assertRaises(CorruptSaveError):
            SaveManager.load_game(self.path, self.loader)

    def test_failed_save_keeps_the_previous_save_intact(self):
        SaveManager.save_game(self.state, self.path)
        before = self.path.read_text()
        self.state.trainer.earn(1000)
        with mock.patch("src.save_manager.json.dump", side_effect=OSError("disk full")):
            with self.assertRaises(SaveWriteError):
                SaveManager.save_game(self.state, self.path)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [self.path], "no temp file left behind")


class TestUIHandlesErrors(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "save.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_title_screen_reports_a_damaged_save(self):
        self.path.write_text("garbage", encoding="utf-8")
        engine = GameEngine(save_path=self.path)
        title = TitleScene(engine)
        self.assertNotIn("CONTINUE", title.options)
        self.assertTrue(title.warning, "the player is told the save is damaged")
        title.update(0.1)
        title.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        title.draw(engine.native_surface)

    def test_overworld_reports_a_failed_save(self):
        self.path.mkdir()  # a folder where the file should go: writing fails
        engine = GameEngine(save_path=self.path)
        ow = OverworldScene(engine)
        engine.push_scene(ow)
        self.assertFalse(ow.save_game())
        ow.mode = "MENU"
        ow.pause_menu.selected_index = ow.pause_menu.options.index("SAVE")
        ow.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
        self.assertIn("failed", ow.notification_text.lower())


if __name__ == "__main__":
    unittest.main()
