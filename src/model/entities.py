"""Things on a map the player can talk to or inspect.

    Interactable (abstract)          has a position, blocks movement, interact()
    ├── Sign                         shows its text
    └── Character (abstract)         has a name and a facing direction
        └── NPC                      turns to face you and talks
            └── Healer               talks, then heals your whole party

Later phases add more subclasses (Professor, TrainerNPC, GymLeader) without
changing the overworld: it just calls ``interact()``.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Tuple, Type

from src.model.direction import Direction

if TYPE_CHECKING:
    from src.model.trainer import Trainer


@dataclass(frozen=True)
class Interaction:
    """The result of interacting with something: who speaks, what they say, and any side effect."""
    speaker: str
    lines: Tuple[str, ...]
    effect: Optional[str] = None


class Interactable(ABC):
    """Abstract base for anything on a map the player can face and press A on."""

    KIND: str = ""
    _registry: Dict[str, Type["Interactable"]] = {}

    def __init__(self, x: int, y: int):
        self._x = x
        self._y = y

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.KIND:
            Interactable._registry[cls.KIND] = cls

    @property
    def position(self) -> Tuple[int, int]:
        return self._x, self._y

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def blocks_movement(self) -> bool:
        return True

    @abstractmethod
    def interact(self, trainer: "Trainer", player_facing: Direction) -> Interaction:
        """React to the player, who is facing ``player_facing`` towards this object."""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "Interactable":
        """Factory: build the subclass registered under ``data["kind"]``."""
        kind = data.get("kind", "")
        sub = cls._registry.get(kind)
        if sub is None:
            raise ValueError(f"Unknown entity kind '{kind}'")
        return sub._from_data(data)

    @classmethod
    @abstractmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Interactable":
        """Build an instance of this subclass from map data."""


class Sign(Interactable):
    """A signpost: shows its text when read."""
    KIND = "sign"

    def __init__(self, x: int, y: int, lines: Sequence[str]):
        super().__init__(x, y)
        self._lines = tuple(lines)

    @property
    def lines(self) -> Tuple[str, ...]:
        return self._lines

    def interact(self, trainer: "Trainer", player_facing: Direction) -> Interaction:
        return Interaction("", self._lines)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Sign":
        return cls(data["x"], data["y"], data.get("lines", []))


class Character(Interactable, ABC):
    """A person on the map: has a name, faces a direction, and is drawn with a colour palette."""

    def __init__(self, x: int, y: int, name: str, facing: Direction = Direction.DOWN,
                 palette: str = "green"):
        super().__init__(x, y)
        self._name = name
        self._facing = facing
        self._palette = palette

    @property
    def name(self) -> str:
        return self._name

    @property
    def facing(self) -> Direction:
        return self._facing

    @property
    def palette(self) -> str:
        return self._palette

    def turn_to(self, player_facing: Direction) -> None:
        """Turn to look at a player who is facing ``player_facing``."""
        self._facing = player_facing.opposite


class NPC(Character):
    """A townsperson who turns to face you and says their lines."""
    KIND = "npc"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str],
                 facing: Direction = Direction.DOWN, palette: str = "green"):
        super().__init__(x, y, name, facing, palette)
        self._lines = tuple(lines)

    @property
    def lines(self) -> Tuple[str, ...]:
        return self._lines

    def interact(self, trainer: "Trainer", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        return Interaction(self._name, self._lines)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "NPC":
        return cls(data["x"], data["y"], data.get("name", "???"), data.get("lines", []),
                   Direction.from_name(data.get("facing", "down")), data.get("palette", "green"))


class Healer(NPC):
    """The healing-center nurse: greets you, heals the whole party, says goodbye."""
    KIND = "healer"

    FAREWELL = ("Your creatures are fully rested.", "Come back any time!")

    def interact(self, trainer: "Trainer", player_facing: Direction) -> Interaction:
        greeting = super().interact(trainer, player_facing)
        trainer.party.heal_all()
        return Interaction(self._name, greeting.lines + self.FAREWELL, effect="healed")

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Healer":
        data = dict(data)
        data.setdefault("palette", "pink")
        return super()._from_data(data)
