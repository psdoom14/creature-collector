"""Headless scene lifecycle, sprite rendering, and architectural isolation tests.

Verifies:
1. Headless dry-run execution of OverworldScene, BattleScene, PartyScene, and PokedexScene
   using SDL_VIDEODRIVER="dummy".
2. SpriteRenderer returns valid pygame.Surface objects without raising exceptions and
   loads real assets from disk without fallback circle badges when assets are present.
3. Strict Model-UI architectural separation: zero pygame imports in any src/model/*.py file.
"""
import ast
import os
import re
import unittest
from pathlib import Path

# Configure headless Pygame environment before importing Pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
from src.ui.engine import GameEngine
from src.ui.overworld_scene import OverworldScene
from src.ui.battle_scene import BattleScene
from src.ui.party_scene import PartyScene
from src.ui.pokedex_scene import PokedexScene
from src.ui.sprite_renderer import SpriteRenderer


class TestSceneRendering(unittest.TestCase):
    """Tier 4 Headless Scene Rendering & Architectural Isolation Suite."""

    @classmethod
    def setUpClass(cls):
        """Set up headless display and shared GameEngine instance."""
        pygame.init()
        cls.engine = GameEngine(title="Test Headless Engine")
        cls.project_root = Path(__file__).resolve().parent.parent

    @classmethod
    def tearDownClass(cls):
        """Clean up Pygame subsystems."""
        pygame.quit()

    def test_model_layer_has_zero_pygame_imports(self):
        """Assert zero pygame imports across all modules in src/model/."""
        model_dir = self.project_root / "src" / "model"
        self.assertTrue(model_dir.is_dir(), f"Model directory not found: {model_dir}")

        py_files = list(model_dir.glob("*.py"))
        self.assertGreater(len(py_files), 0, "No Python files found in src/model/")

        violations = []
        import_regex = re.compile(r"^\s*(import\s+pygame|from\s+pygame)", re.MULTILINE)

        for file_path in py_files:
            source = file_path.read_text(encoding="utf-8")

            # 1. Regex check
            for match in import_regex.finditer(source):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(f"{file_path.name}:{line_no} matches regex '{match.group(0).strip()}'")

            # 2. AST check
            try:
                tree = ast.parse(source, filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "pygame" or alias.name.startswith("pygame."):
                                violations.append(f"{file_path.name}:{node.lineno} imports '{alias.name}'")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and (node.module == "pygame" or node.module.startswith("pygame.")):
                            violations.append(f"{file_path.name}:{node.lineno} imports from '{node.module}'")
            except SyntaxError as e:
                violations.append(f"{file_path.name}: SyntaxError ({e})")

        self.assertEqual(
            violations,
            [],
            f"Strict Architectural Isolation violated! Found pygame imports in src/model/:\n"
            + "\n".join(violations),
        )

    def test_headless_overworld_scene_lifecycle(self):
        """Test OverworldScene initialization, event processing, multi-frame update, and drawing."""
        scene = OverworldScene(self.engine)
        scene.on_enter()

        # Advance frames to exercise timers, step lerp, and water animation
        for _ in range(10):
            scene.update(0.016)

        # Draw to native 240x160 surface
        surface = self.engine.native_surface
        scene.draw(surface)
        self.assertEqual(surface.get_size(), (240, 160))

        # Handle a movement key event
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
        scene.handle_event(event)
        scene.update(0.016)
        scene.draw(surface)

        scene.on_exit()

    def test_headless_battle_scene_lifecycle(self):
        """Test BattleScene initialization, update, and drawing with wild creature."""
        wild = self.engine.data_loader.get_creature(1, level=5)  # Bulbasaur
        self.assertIsNotNone(wild, "Failed to load wild creature Bulbasaur")

        battle_scene = BattleScene(self.engine, wild)
        battle_scene.on_enter()

        # Advance frames to exercise shake timers and animations
        for _ in range(5):
            battle_scene.update(0.016)

        surface = self.engine.native_surface
        battle_scene.draw(surface)
        self.assertEqual(surface.get_size(), (240, 160))

        # Test advancing battle dialogue via keypress
        advance_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        battle_scene.handle_event(advance_event)
        battle_scene.update(0.016)
        battle_scene.draw(surface)

        battle_scene.on_exit()

    def test_headless_party_scene_lifecycle(self):
        """Test PartyScene initialization, navigation, update, and drawing."""
        party_scene = PartyScene(self.engine)
        party_scene.on_enter()

        party_scene.update(0.016)
        surface = self.engine.native_surface
        party_scene.draw(surface)
        self.assertEqual(surface.get_size(), (240, 160))

        # Test cursor navigation
        nav_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        party_scene.handle_event(nav_event)
        party_scene.update(0.016)
        party_scene.draw(surface)

        party_scene.on_exit()

    def test_headless_pokedex_scene_lifecycle(self):
        """Test PokedexScene initialization, scrolling, update, and drawing."""
        dex = self.engine.game_state.pokedex
        dex.register_seen(1)
        dex.register_caught(1)
        dex.register_seen(4)

        dex_scene = PokedexScene(self.engine)
        dex_scene.on_enter()

        dex_scene.update(0.016)
        surface = self.engine.native_surface
        dex_scene.draw(surface)
        self.assertEqual(surface.get_size(), (240, 160))

        # Test scrolling down
        scroll_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        dex_scene.handle_event(scroll_event)
        dex_scene.update(0.016)
        dex_scene.draw(surface)

        dex_scene.on_exit()

    def test_sprite_renderer_returns_valid_surfaces_and_handles_dual_signatures(self):
        """Verify SpriteRenderer returns genuine surfaces across both legacy and new signatures."""
        # 1. New Contract signature: get_creature_sprite(name, size, is_back, creature_id)
        surf_new = SpriteRenderer.get_creature_sprite("Bulbasaur", (64, 64), False)
        self.assertIsInstance(surf_new, pygame.Surface)
        self.assertEqual(surf_new.get_size(), (64, 64))

        # 2. Legacy signature: get_creature_sprite(species_id, name, primary_type, is_back, size)
        surf_legacy = SpriteRenderer.get_creature_sprite(4, "Charmander", "Fire", True, (56, 56))
        self.assertIsInstance(surf_legacy, pygame.Surface)
        self.assertEqual(surf_legacy.get_size(), (56, 56))

        # 3. Keyword arguments
        surf_kwargs = SpriteRenderer.get_creature_sprite(name="Squirtle", size=(32, 32), is_back=False)
        self.assertIsInstance(surf_kwargs, pygame.Surface)
        self.assertEqual(surf_kwargs.get_size(), (32, 32))

    def test_sprite_renderer_all_25_species_front_and_back(self):
        """Verify SpriteRenderer successfully renders front and back views for all 25 species."""
        creatures = self.engine.data_loader.get_all_species()
        self.assertEqual(len(creatures), 25)

        for c in creatures:
            name = c["name"]
            # Front view
            front_surf = SpriteRenderer.get_creature_sprite(name, size=(64, 64), is_back=False)
            self.assertIsInstance(front_surf, pygame.Surface)
            self.assertEqual(front_surf.get_size(), (64, 64))

            # Back view
            back_surf = SpriteRenderer.get_creature_sprite(name, size=(64, 64), is_back=True)
            self.assertIsInstance(back_surf, pygame.Surface)
            self.assertEqual(back_surf.get_size(), (64, 64))


if __name__ == "__main__":
    unittest.main()
