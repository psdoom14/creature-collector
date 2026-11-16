"""Type chart and effectiveness calculations."""
from typing import Dict, List, Optional
import json
from pathlib import Path


class TypeChart:
    """Represents the type effectiveness relationship in the creature world."""

    def __init__(self, chart_data: Optional[Dict[str, Dict[str, float]]] = None):
        self._chart: Dict[str, Dict[str, float]] = chart_data or {}

    @classmethod
    def from_file(cls, filepath: str | Path) -> "TypeChart":
        """Load type effectiveness data from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def get_multiplier(self, attacking_type: str, defending_type: str) -> float:
        """Get effectiveness multiplier of an attacking type against a single defending type."""
        atk = attacking_type.capitalize()
        dfn = defending_type.capitalize()

        if atk in self._chart and dfn in self._chart[atk]:
            return self._chart[atk][dfn]
        return 1.0

    def get_effectiveness(self, attacking_type: str, defending_types: List[str]) -> float:
        """Calculate the combined effectiveness multiplier against one or two defending types."""
        multiplier = 1.0
        for dfn in defending_types:
            multiplier *= self.get_multiplier(attacking_type, dfn)
        return multiplier

    def get_effectiveness_message(self, multiplier: float) -> Optional[str]:
        """Return classic combat message based on damage multiplier."""
        if multiplier == 0.0:
            return "It had no effect!"
        if multiplier > 1.0:
            return "It's super effective!"
        if multiplier < 1.0:
            return "It's not very effective..."
        return None
