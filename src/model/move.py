"""Moves as a class hierarchy.

    Move (abstract)
    ├── DamagingMove (abstract)
    │   ├── PhysicalMove   uses Attack vs Defense
    │   └── SpecialMove    uses Sp. Atk vs Sp. Def
    └── StatusMove         no damage, only an effect
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.model.move_effect import MoveEffect

if TYPE_CHECKING:
    from src.model.creature import Creature


class Move(ABC):
    """Abstract base class for a move a creature can use in battle."""

    CATEGORY: str = ""

    def __init__(
        self,
        move_id: str,
        name: str,
        move_type: str,
        power: int,
        accuracy: int,
        pp: int,
        effect: Optional[MoveEffect] = None,
        current_pp: Optional[int] = None,
    ):
        self._id = move_id
        self._name = name
        self._type = move_type.capitalize()
        self._power = power
        self._accuracy = accuracy
        self._max_pp = pp
        self._current_pp = pp if current_pp is None else max(0, min(pp, current_pp))
        self._effect = effect

    # --- read-only data ------------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def category(self) -> str:
        return self.CATEGORY

    @property
    def power(self) -> int:
        return self._power

    @property
    def accuracy(self) -> int:
        return self._accuracy

    @property
    def max_pp(self) -> int:
        return self._max_pp

    @property
    def current_pp(self) -> int:
        return self._current_pp

    @property
    def effect(self) -> Optional[MoveEffect]:
        return self._effect

    # --- PP ------------------------------------------------------------
    def can_use(self) -> bool:
        """Check if move has remaining PP."""
        return self._current_pp > 0

    def use(self) -> bool:
        """Spend 1 PP. Returns False if there was none left."""
        if self.can_use():
            self._current_pp -= 1
            return True
        return False

    def restore_pp(self, amount: Optional[int] = None) -> int:
        """Restore PP (fully if ``amount`` is None). Returns PP restored."""
        old = self._current_pp
        target = self._max_pp if amount is None else self._current_pp + amount
        self._current_pp = min(self._max_pp, target)
        return self._current_pp - old

    # --- polymorphic behaviour ----------------------------------------
    @abstractmethod
    def is_damaging(self) -> bool:
        """Whether this move deals direct HP damage."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._id,
            "name": self._name,
            "type": self._type,
            "category": self.category,
            "power": self._power,
            "accuracy": self._accuracy,
            "pp": self._max_pp,
            "current_pp": self._current_pp,
            "effect": self._effect.key if self._effect else None,
            "effect_chance": self._effect.chance if self._effect else 0,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name} ({self._type}) PP:{self._current_pp}/{self._max_pp}>"


class DamagingMove(Move, ABC):
    """A move that deals damage. Subclasses choose which stats it uses."""

    def is_damaging(self) -> bool:
        return True

    @abstractmethod
    def attack_stat(self, user: "Creature") -> int:
        """The user's stat that powers this move."""

    @abstractmethod
    def defense_stat(self, target: "Creature") -> int:
        """The target's stat that resists this move."""


class PhysicalMove(DamagingMove):
    """Contact-style move: Attack vs Defense."""
    CATEGORY = "physical"

    def attack_stat(self, user: "Creature") -> int:
        return user.attack

    def defense_stat(self, target: "Creature") -> int:
        return target.defense


class SpecialMove(DamagingMove):
    """Energy-style move: Sp. Atk vs Sp. Def."""
    CATEGORY = "special"

    def attack_stat(self, user: "Creature") -> int:
        return user.sp_attack

    def defense_stat(self, target: "Creature") -> int:
        return target.sp_defense


class StatusMove(Move):
    """A move with no damage that only applies its effect."""
    CATEGORY = "status"

    def is_damaging(self) -> bool:
        return False


class MoveFactory:
    """Factory that builds the right Move subclass from a data dictionary."""

    _CLASSES = {"physical": PhysicalMove, "special": SpecialMove, "status": StatusMove}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Move:
        category = data.get("category", "physical").lower()
        move_cls = cls._CLASSES.get(category)
        if move_cls is None:
            raise ValueError(f"Unknown move category '{category}' for move '{data.get('id')}'")
        return move_cls(
            move_id=data["id"],
            name=data["name"],
            move_type=data["type"],
            power=data.get("power", 0),
            accuracy=data.get("accuracy", 100),
            pp=data.get("pp", 20),
            effect=MoveEffect.from_data(data.get("effect"), data.get("effect_chance", 0)),
            current_pp=data.get("current_pp"),
        )

    @classmethod
    def struggle(cls) -> Move:
        """The fallback move used when a creature has no PP left."""
        return PhysicalMove("struggle", "Struggle", "Normal", power=50, accuracy=100, pp=1)
