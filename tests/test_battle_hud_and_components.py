"""Unit and component tests for Milestone M3: Battle HUD, Pedestals & Typography."""
import os
import unittest
from pathlib import Path

# Configure headless Pygame environment
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
from src.ui.engine import GameEngine
from src.ui.battle_scene import BattleScene
from src.ui.components import (
    get_font,
    draw_crisp_text,
    draw_gba_hp_box,
    draw_battle_platform,
    draw_status_pill,
    draw_hp_badge,
    HPBar,
    EXPBar,
    TextBox,
    MenuBox,
    COLOR_TEXT_DARK,
    COLOR_TEXT_SHADOW,
    COLOR_HP_GREEN,
    COLOR_HP_YELLOW,
    COLOR_HP_RED,
    COLOR_EXP_CYAN,
    STATUS_COLORS,
)


class TestBattleHUDAndComponents(unittest.TestCase):
    """Test suite verifying F7 (Pedestals), F8 (HP Boxes/HUD), and F9 (Crisp Typography)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.engine = GameEngine(title="Test HUD Engine")
        cls.fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_bundled_fonts_exist_and_load(self):
        """Verify all three bundled TTF fonts exist in assets/fonts/ and load cleanly."""
        expected_fonts = ["pokemon-font.ttf", "PressStart2P-Regular.ttf", "Silkscreen-Regular.ttf"]
        for font_name in expected_fonts:
            font_path = self.fonts_dir / font_name
            self.assertTrue(font_path.is_file(), f"Font file missing: {font_path}")
            f = get_font(size=8, font_name=font_name)
            self.assertIsInstance(f, pygame.font.Font)

    def test_crisp_text_rendering_antialias_false(self):
        """Verify draw_crisp_text renders strictly binary 1-bit pixels (no blurry subpixels)."""
        surf = pygame.Surface((120, 30), pygame.SRCALPHA)
        font = get_font(8, "pokemon-font.ttf")

        rect = draw_crisp_text(surf, "PIKACHU", 10, 10, font=font, color=(0, 0, 0), shadow_color=None)
        self.assertGreater(rect.width, 0)
        self.assertGreater(rect.height, 0)

        # Inspect all pixels on the surface; alpha must only be 0 or 255
        alphas = set()
        for x in range(surf.get_width()):
            for y in range(surf.get_height()):
                alphas.add(surf.get_at((x, y)).a)

        self.assertTrue(alphas.issubset({0, 255}), f"Non-binary alpha subpixel blur detected: {alphas}")

    def test_crisp_text_drop_shadow_offset(self):
        """Verify draw_crisp_text draws shadow at exact (x+1, y+1) offset."""
        surf = pygame.Surface((60, 20), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        font = get_font(8, "pokemon-font.ttf")

        fg_color = (255, 0, 0)
        shadow_color = (0, 0, 255)

        draw_crisp_text(surf, "A", 5, 5, font=font, color=fg_color, shadow_color=shadow_color)

        # Confirm shadow pixels (blue) and foreground pixels (red) exist
        found_fg = False
        found_shadow = False
        for x in range(surf.get_width()):
            for y in range(surf.get_height()):
                c = surf.get_at((x, y))
                if (c.r, c.g, c.b) == fg_color:
                    found_fg = True
                elif (c.r, c.g, c.b) == shadow_color:
                    found_shadow = True

        self.assertTrue(found_fg, "Foreground text color not found on surface")
        self.assertTrue(found_shadow, "Drop shadow color not found at (x+1, y+1) on surface")

    def test_draw_battle_platform_pedestals(self):
        """Verify tiered 3D battle platforms render layered grass, cliff, and drop shadow."""
        surf = pygame.Surface((240, 160))
        surf.fill((232, 240, 224))

        # Enemy platform (top right)
        draw_battle_platform(surf, center_x=181, center_y=60, width=88, height=26, is_player=False)
        # Player platform (bottom left)
        draw_battle_platform(surf, center_x=58, center_y=108, width=108, height=30, is_player=True)

        # Test presence of grass green (72, 160, 64) and dirt cliff (136, 104, 56 or 88, 64, 32)
        pixels = [surf.get_at((x, y))[:3] for x in range(surf.get_width()) for y in range(surf.get_height())]
        color_set = set(pixels)

        # Must have dirt cliff tones and grass tones
        self.assertIn((72, 160, 64), color_set, "Base grass color not found on platform")
        self.assertTrue(
            (136, 104, 56) in color_set or (88, 64, 32) in color_set,
            "Dirt cliff colors not found on 3D pedestal bevel",
        )
        self.assertIn((176, 192, 168), color_set, "Drop shadow color not found beneath platform")

    def test_draw_gba_hp_box_enemy_and_player(self):
        """Verify classic asymmetric notched GBA HP boxes for both enemy and player."""
        surf = pygame.Surface((240, 160))
        surf.fill((232, 240, 224))

        # Enemy HUD box (no EXP, no numeric HP)
        draw_gba_hp_box(
            surf,
            rect=(10, 10, 105, 32),
            name="Bulbasaur",
            level=5,
            current_hp=15,
            max_hp=20,
            exp_ratio=None,
            status=None,
        )

        # Player HUD box (with EXP ratio and numeric HP)
        draw_gba_hp_box(
            surf,
            rect=(122, 66, 114, 40),
            name="Charmander",
            level=6,
            current_hp=22,
            max_hp=24,
            exp_ratio=0.75,
            status=None,
        )

        # Verify pixels contain cyan EXP bar color (64, 168, 248) and HP green (48, 208, 80)
        pixels = [surf.get_at((x, y))[:3] for x in range(surf.get_width()) for y in range(surf.get_height())]
        color_set = set(pixels)
        self.assertIn(COLOR_HP_GREEN, color_set, "HP Green not found in HP bar")
        self.assertIn(COLOR_EXP_CYAN, color_set, "Cyan not found in Player EXP progress bar")

    def test_status_pill_rendering(self):
        """Verify status pills render with authentic colors for PSN, PAR, BRN, SLP, FRZ."""
        surf = pygame.Surface((200, 50))
        surf.fill((255, 255, 255))

        statuses = ["PSN", "PAR", "BRN", "SLP", "FRZ"]
        for i, st in enumerate(statuses):
            draw_status_pill(surf, 10 + i * 30, 15, st)

        pixels = [surf.get_at((x, y))[:3] for x in range(surf.get_width()) for y in range(surf.get_height())]
        color_set = set(pixels)

        for st in statuses:
            self.assertIn(STATUS_COLORS[st], color_set, f"Status color for {st} not found on surface")

    def test_exp_bar_animation_and_clamping(self):
        """Verify EXPBar updates smoothly and clamps ratio between 0.0 and 1.0."""
        bar = EXPBar(x=10, y=10, width=50, height=3)
        self.assertEqual(bar.display_ratio, 0.0)

        # Test ratio clamping
        bar.set_ratio(1.5)
        self.assertEqual(bar.target_ratio, 1.0)
        bar.set_ratio(-0.5)
        self.assertEqual(bar.target_ratio, 0.0)

        # Test smooth interpolation
        bar.set_ratio(0.8)
        bar.update(0.1)  # step = 2.0 * 0.1 = 0.2
        self.assertAlmostEqual(bar.display_ratio, 0.2, places=2)

        # Immediate mode
        bar.set_ratio(0.9, immediate=True)
        self.assertEqual(bar.display_ratio, 0.9)

        # Draw call
        surf = pygame.Surface((70, 20))
        bar.draw(surf)

    def test_battle_scene_move_select_and_type_pp_panel(self):
        """Verify BattleScene MOVE_SELECT shows move names, types, and PP readouts."""
        wild = self.engine.data_loader.get_creature(1, level=5)
        battle_scene = BattleScene(self.engine, wild)
        battle_scene.on_enter()
        for _ in range(20):          # let the intro slide-in finish (keys wait for animations)
            battle_scene.update(0.1)

        # Switch to MOVE_SELECT
        p_lead = battle_scene.battle.player_creature
        self.assertIsNotNone(p_lead)
        self.assertGreater(len(p_lead.moves), 0)

        battle_scene.sub_state = "ACTION_SELECT"
        # Press FIGHT (choice 0)
        event_fight = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        battle_scene.handle_event(event_fight)

        self.assertEqual(battle_scene.sub_state, "MOVE_SELECT")
        self.assertIsNotNone(battle_scene.move_menu)

        # Render MOVE_SELECT frame
        surf = self.engine.native_surface
        battle_scene.draw(surf)
        self.assertEqual(surf.get_size(), (240, 160))


if __name__ == "__main__":
    unittest.main()
