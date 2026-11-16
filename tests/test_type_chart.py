"""Tests for type effectiveness calculation."""
import unittest
from pathlib import Path
from src.model.type_chart import TypeChart


class TestTypeChart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parent.parent / "data" / "type_chart.json"
        cls.chart = TypeChart.from_file(path)

    def test_super_effective(self):
        # Water is 2x against Fire
        mult = self.chart.get_effectiveness("Water", ["Fire"])
        self.assertEqual(mult, 2.0)
        self.assertEqual(self.chart.get_effectiveness_message(mult), "It's super effective!")

    def test_not_very_effective(self):
        # Fire is 0.5x against Water
        mult = self.chart.get_effectiveness("Fire", ["Water"])
        self.assertEqual(mult, 0.5)
        self.assertEqual(self.chart.get_effectiveness_message(mult), "It's not very effective...")

    def test_immunity(self):
        # Normal against Ghost is 0x
        mult = self.chart.get_effectiveness("Normal", ["Ghost"])
        self.assertEqual(mult, 0.0)
        self.assertEqual(self.chart.get_effectiveness_message(mult), "It had no effect!")

    def test_dual_type_quad_weakness(self):
        # Grass against Water/Ground is 2.0 * 2.0 = 4.0
        mult = self.chart.get_effectiveness("Grass", ["Water", "Ground"])
        self.assertEqual(mult, 4.0)

    def test_neutral_effectiveness(self):
        # Normal against Normal is 1.0x
        mult = self.chart.get_effectiveness("Normal", ["Normal"])
        self.assertEqual(mult, 1.0)
        self.assertIsNone(self.chart.get_effectiveness_message(mult))


if __name__ == "__main__":
    unittest.main()
