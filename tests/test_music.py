"""Background music: the right track for each screen, looping, and never a crash without sound."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.ui.music import MUSIC_DIR, TRACKS, MusicPlayer


class FakeDevice:
    """Stands in for pygame.mixer.music and records what it was asked to do."""

    def __init__(self):
        self.loaded = []
        self.plays = []
        self.stopped = 0
        self.volume = None

    def set_volume(self, v):
        self.volume = v

    def fadeout(self, ms):
        pass

    def load(self, path):
        self.loaded.append(Path(path).name)

    def play(self, loops=0, fade_ms=0):
        self.plays.append(loops)

    def stop(self):
        self.stopped += 1


class MusicPlayerTests(unittest.TestCase):
    def test_every_track_file_exists(self):
        for track, filename in TRACKS.items():
            self.assertTrue((MUSIC_DIR / filename).exists(), track)

    def test_plays_in_a_loop_and_does_not_restart_the_same_track(self):
        dev = FakeDevice()
        player = MusicPlayer(device=dev)
        player.play("world")
        player.play("world")
        self.assertEqual(dev.loaded, ["world.mp3"])
        self.assertEqual(dev.plays, [-1])              # -1 = loop forever

    def test_switching_tracks(self):
        dev = FakeDevice()
        player = MusicPlayer(device=dev)
        for track in ("menu", "world", "battle", "world"):
            player.play(track)
        self.assertEqual(dev.loaded, ["menu.wav", "world.mp3", "battle.mp3", "world.mp3"])

    def test_mute_stops_and_unmute_resumes(self):
        dev = FakeDevice()
        player = MusicPlayer(device=dev)
        player.play("battle")
        self.assertTrue(player.toggle_mute())
        self.assertEqual(dev.stopped, 1)
        player.play("world")                           # remembered, not played while muted
        self.assertEqual(dev.loaded, ["battle.mp3"])
        self.assertFalse(player.toggle_mute())
        self.assertEqual(dev.loaded, ["battle.mp3", "world.mp3"])

    def test_no_sound_device_is_silent_not_a_crash(self):
        player = MusicPlayer(enabled=False)
        self.assertFalse(player.available)
        player.play("world")
        player.toggle_mute()
        player.stop()
        self.assertIsNone(player.current)

    def test_missing_file_is_skipped(self):
        dev = FakeDevice()
        with tempfile.TemporaryDirectory() as empty:
            player = MusicPlayer(device=dev, music_dir=Path(empty))
            player.play("world")
        self.assertEqual(dev.loaded, [])


class ScreenMusicTests(unittest.TestCase):
    """The engine plays the track of the topmost screen that names one."""

    def setUp(self):
        from src.ui.engine import GameEngine
        pygame.init()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.dev = FakeDevice()
        self.engine.music = MusicPlayer(device=self.dev)

    def tearDown(self):
        self.tmp.cleanup()

    def test_title_world_menus_and_battle(self):
        from src.ui.bag_scene import BagScene
        from src.ui.battle_scene import BattleScene
        from src.ui.overworld_scene import OverworldScene
        from src.ui.title_scene import TitleScene
        from src.ui.transitions import TransitionScene, WildTransition
        e = self.engine
        e.push_scene(TitleScene(e))
        self.assertEqual(e.music.current, "menu")
        e.change_scene(OverworldScene(e))
        self.assertEqual(e.music.current, "world")
        e.push_scene(BagScene(e))                      # a pop-up menu keeps the world music
        self.assertEqual(e.music.current, "world")
        e.pop_scene()
        e.game_state.trainer.party.add(e.data_loader.get_creature(4, 5))
        battle = BattleScene(e, e.data_loader.get_creature(16, 3))
        e.push_scene(TransitionScene(e, e.native_surface.copy(), battle, WildTransition()))
        self.assertEqual(e.music.current, "battle")
        e.current_scene.update(10.0)                   # transition ends, battle takes over
        self.assertIs(e.current_scene, battle)
        self.assertEqual(self.dev.loaded, ["menu.wav", "world.mp3", "battle.mp3"])   # battle started once
        e.pop_scene()                                  # back to the overworld
        self.assertEqual(e.music.current, "world")


if __name__ == "__main__":
    unittest.main()
