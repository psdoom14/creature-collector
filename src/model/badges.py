"""Gym badges the player has earned."""
from typing import Iterable, List, Tuple


class BadgeCase:
    """An ordered collection of badge names; each badge can only be earned once."""

    def __init__(self, names: Iterable[str] = ()):
        self._names: List[str] = []
        for name in names:
            self.add(name)

    def add(self, name: str) -> bool:
        """Earn ``name``. Returns False if it was already earned."""
        if name in self._names:
            return False
        self._names.append(name)
        return True

    def has(self, name: str) -> bool:
        return name in self._names

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(self._names)

    @property
    def count(self) -> int:
        return len(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def to_list(self) -> List[str]:
        return list(self._names)

    @classmethod
    def from_list(cls, names: Iterable[str]) -> "BadgeCase":
        return cls(names)
