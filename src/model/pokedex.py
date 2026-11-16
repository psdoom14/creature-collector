"""Pokédex model to track encountered and captured species."""
from typing import Set, Tuple, Dict, Any, Optional


class Pokedex:
    """Tracks seen and caught species across the game."""

    def __init__(
        self,
        seen: Optional[Set[int]] = None,
        caught: Optional[Set[int]] = None,
    ):
        self.seen: Set[int] = seen or set()
        self.caught: Set[int] = caught or set()

    def register_seen(self, species_id: int) -> bool:
        """Mark a species as seen. Returns True if newly seen."""
        if species_id not in self.seen:
            self.seen.add(species_id)
            return True
        return False

    def register_caught(self, species_id: int) -> bool:
        """Mark a species as caught. Also registers as seen."""
        self.register_seen(species_id)
        if species_id not in self.caught:
            self.caught.add(species_id)
            return True
        return False

    def is_seen(self, species_id: int) -> bool:
        return species_id in self.seen

    def is_caught(self, species_id: int) -> bool:
        return species_id in self.caught

    def get_completion(self, total_species: int = 25) -> Tuple[int, int, float]:
        """Returns (caught_count, total_species, percentage)."""
        caught_count = len(self.caught)
        pct = (caught_count / max(1, total_species)) * 100.0
        return caught_count, total_species, round(pct, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seen": sorted(list(self.seen)),
            "caught": sorted(list(self.caught)),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pokedex":
        return cls(
            seen=set(data.get("seen", [])),
            caught=set(data.get("caught", [])),
        )
