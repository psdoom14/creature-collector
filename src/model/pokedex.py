"""Pokédex: which species the player has seen and caught."""
from typing import Any, Dict, FrozenSet, Iterable, Optional, Tuple


class Pokedex:
    """Tracks seen and caught species. Catching a species also marks it seen."""

    def __init__(self, seen: Optional[Iterable[int]] = None, caught: Optional[Iterable[int]] = None):
        self._caught = set(caught or ())
        self._seen = set(seen or ()) | self._caught

    @property
    def seen(self) -> FrozenSet[int]:
        return frozenset(self._seen)

    @property
    def caught(self) -> FrozenSet[int]:
        return frozenset(self._caught)

    @property
    def seen_count(self) -> int:
        return len(self._seen)

    @property
    def caught_count(self) -> int:
        return len(self._caught)

    def register_seen(self, species_id: int) -> bool:
        """Mark a species as seen. Returns True if it is new."""
        if species_id in self._seen:
            return False
        self._seen.add(species_id)
        return True

    def register_caught(self, species_id: int) -> bool:
        """Mark a species as caught (and seen). Returns True if it is new."""
        self._seen.add(species_id)
        if species_id in self._caught:
            return False
        self._caught.add(species_id)
        return True

    def is_seen(self, species_id: int) -> bool:
        return species_id in self._seen

    def is_caught(self, species_id: int) -> bool:
        return species_id in self._caught

    def get_completion(self, total_species: int) -> Tuple[int, int, float]:
        """Returns (caught, total, percent caught)."""
        pct = self.caught_count / max(1, total_species) * 100.0
        return self.caught_count, total_species, round(pct, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {"seen": sorted(self._seen), "caught": sorted(self._caught)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pokedex":
        return cls(seen=data.get("seen", []), caught=data.get("caught", []))
