"""The four walking directions."""
from enum import Enum


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    @property
    def opposite(self) -> "Direction":
        return Direction((-self.dx, -self.dy))

    @property
    def key(self) -> str:
        """Lower-case name used in data files and sprite names ("up", "down", ...)."""
        return self.name.lower()

    @classmethod
    def from_name(cls, name: str) -> "Direction":
        return cls[name.upper()]
