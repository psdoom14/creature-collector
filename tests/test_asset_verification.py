"""Automated verification test suite for all pixel-art assets.

Verifies:
1. 50 Gen-3 creature sprites (25 front + 25 back) for all canonical species in data/creatures.json:
   - File existence at assets/sprites/<name.lower()>_front.png and back.png
   - Valid PNG format
   - Exact 64x64 dimensions
   - Transparent alpha channel
2. 12 16x16 GBA metatiles in assets/tiles/:
   - grass.png, tall_grass.png, tall_grass_overlay.png, path.png, tree.png
   - 4 animated water tiles (water_0.png to water_3.png)
   - 3 PokeCenter facade tiles (pokecenter_left.png, pokecenter_center.png, pokecenter_right.png)
   - Exact 16x16 dimensions & PNG format
3. 12 trainer walk cycle frames in assets/characters/trainer/:
   - 4 directions (down, up, left, right) x 3 animation states (idle, walk1, walk2)
   - Valid PNG format and alpha transparency
"""
import json
import unittest
from pathlib import Path
from PIL import Image


class TestAssetVerification(unittest.TestCase):
    """Tier 4 E2E Asset Integrity & Specification Verification."""

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.creatures_json_path = cls.project_root / "data" / "creatures.json"
        cls.sprites_dir = cls.project_root / "assets" / "sprites"
        cls.tiles_dir = cls.project_root / "assets" / "tiles"
        cls.trainer_dir = cls.project_root / "assets" / "characters" / "trainer"

        with open(cls.creatures_json_path, "r", encoding="utf-8") as f:
            cls.creatures = json.load(f)

    def test_creatures_data_has_25_species(self):
        """Assert data/creatures.json defines exactly the 25 canonical species."""
        self.assertEqual(
            len(self.creatures),
            25,
            f"Expected exactly 25 species in data/creatures.json, found {len(self.creatures)}",
        )

    def test_creature_sprites_files_exist(self):
        """Verify all 25 species have both front and back sprite files on disk."""
        missing_files = []
        for c in self.creatures:
            name = c["name"].lower()
            front_path = self.sprites_dir / f"{name}_front.png"
            back_path = self.sprites_dir / f"{name}_back.png"

            if not front_path.is_file():
                missing_files.append(str(front_path))
            if not back_path.is_file():
                missing_files.append(str(back_path))

        self.assertEqual(
            missing_files,
            [],
            f"Missing {len(missing_files)} creature sprite files:\n" + "\n".join(missing_files),
        )

    def test_creature_sprites_dimensions_and_png_format(self):
        """Verify all 50 creature sprites are valid PNGs with exact 64x64 dimensions."""
        invalid_sprites = []
        for c in self.creatures:
            name = c["name"].lower()
            for view in ("front", "back"):
                sprite_path = self.sprites_dir / f"{name}_{view}.png"
                if not sprite_path.is_file():
                    continue

                try:
                    with Image.open(sprite_path) as img:
                        if img.format != "PNG":
                            invalid_sprites.append(f"{sprite_path.name}: format is {img.format}, expected PNG")
                        if img.size != (64, 64):
                            invalid_sprites.append(f"{sprite_path.name}: dimensions {img.size}, expected (64, 64)")
                except Exception as exc:
                    invalid_sprites.append(f"{sprite_path.name}: failed to open ({exc})")

        self.assertEqual(
            invalid_sprites,
            [],
            f"Found invalid creature sprites:\n" + "\n".join(invalid_sprites),
        )

    def test_creature_sprites_have_alpha_transparency(self):
        """Verify all 50 creature sprites have genuine alpha transparency."""
        lacking_alpha = []
        for c in self.creatures:
            name = c["name"].lower()
            for view in ("front", "back"):
                sprite_path = self.sprites_dir / f"{name}_{view}.png"
                if not sprite_path.is_file():
                    continue

                with Image.open(sprite_path) as img:
                    has_alpha_channel = (
                        img.mode in ("RGBA", "LA")
                        or (img.mode == "P" and "transparency" in img.info)
                    )
                    if not has_alpha_channel:
                        lacking_alpha.append(f"{sprite_path.name}: mode {img.mode} has no alpha channel")
                        continue

                    # Verify at least one pixel is transparent (< 255 alpha)
                    converted = img.convert("RGBA")
                    alpha_extrema = converted.getextrema()[3]  # (min_alpha, max_alpha)
                    if alpha_extrema[0] == 255:
                        lacking_alpha.append(f"{sprite_path.name}: entirely opaque (no transparent pixels)")

        self.assertEqual(
            lacking_alpha,
            [],
            f"Sprites lacking transparent alpha:\n" + "\n".join(lacking_alpha),
        )

    def test_gba_tiles_exist_and_match_spec(self):
        """Verify all 16x16 GBA tiles exist in assets/tiles/."""
        expected_tiles = [
            "grass.png",
            "tall_grass.png",
            "tall_grass_overlay.png",
            "path.png",
            "tree.png",
            "water_0.png",
            "water_1.png",
            "water_2.png",
            "water_3.png",
            "pokecenter_left.png",
            "pokecenter_center.png",
            "pokecenter_right.png",
        ]
        missing_tiles = []
        for tile_name in expected_tiles:
            tile_path = self.tiles_dir / tile_name
            if not tile_path.is_file():
                missing_tiles.append(tile_name)

        self.assertEqual(
            missing_tiles,
            [],
            f"Missing overworld tile files in assets/tiles/: {missing_tiles}",
        )

    def test_gba_tiles_dimensions_and_png_format(self):
        """Verify all 12 GBA tiles are valid 16x16 PNG images."""
        expected_tiles = [
            "grass.png",
            "tall_grass.png",
            "tall_grass_overlay.png",
            "path.png",
            "tree.png",
            "water_0.png",
            "water_1.png",
            "water_2.png",
            "water_3.png",
            "pokecenter_left.png",
            "pokecenter_center.png",
            "pokecenter_right.png",
        ]
        invalid_tiles = []
        for tile_name in expected_tiles:
            tile_path = self.tiles_dir / tile_name
            if not tile_path.is_file():
                continue

            try:
                with Image.open(tile_path) as img:
                    if img.format != "PNG":
                        invalid_tiles.append(f"{tile_name}: format is {img.format}, expected PNG")
                    if img.size != (16, 16):
                        invalid_tiles.append(f"{tile_name}: size is {img.size}, expected (16, 16)")
            except Exception as exc:
                invalid_tiles.append(f"{tile_name}: failed to open ({exc})")

        self.assertEqual(
            invalid_tiles,
            [],
            f"Invalid tile images in assets/tiles/:\n" + "\n".join(invalid_tiles),
        )

    def test_trainer_walk_cycle_frames_exist(self):
        """Verify all 12 trainer walk cycle frames exist in assets/characters/trainer/."""
        directions = ("down", "up", "left", "right")
        states = ("idle", "walk1", "walk2")
        missing_frames = []

        for d in directions:
            for s in states:
                frame_name = f"trainer_{d}_{s}.png"
                frame_path = self.trainer_dir / frame_name
                if not frame_path.is_file():
                    missing_frames.append(frame_name)

        self.assertEqual(
            missing_frames,
            [],
            f"Missing trainer walk cycle frames: {missing_frames}",
        )

    def test_trainer_walk_cycle_format_and_transparency(self):
        """Verify all 12 trainer frames are valid PNGs with transparent alpha."""
        directions = ("down", "up", "left", "right")
        states = ("idle", "walk1", "walk2")
        invalid_frames = []

        for d in directions:
            for s in states:
                frame_name = f"trainer_{d}_{s}.png"
                frame_path = self.trainer_dir / frame_name
                if not frame_path.is_file():
                    continue

                try:
                    with Image.open(frame_path) as img:
                        if img.format != "PNG":
                            invalid_frames.append(f"{frame_name}: format is {img.format}, expected PNG")
                        has_alpha = (
                            img.mode in ("RGBA", "LA")
                            or (img.mode == "P" and "transparency" in img.info)
                        )
                        if not has_alpha:
                            invalid_frames.append(f"{frame_name}: mode {img.mode} has no alpha")
                        else:
                            converted = img.convert("RGBA")
                            if converted.getextrema()[3][0] == 255:
                                invalid_frames.append(f"{frame_name}: entirely opaque")
                except Exception as exc:
                    invalid_frames.append(f"{frame_name}: failed to open ({exc})")

        self.assertEqual(
            invalid_frames,
            [],
            f"Invalid trainer frames in assets/characters/trainer/:\n" + "\n".join(invalid_frames),
        )


if __name__ == "__main__":
    unittest.main()
