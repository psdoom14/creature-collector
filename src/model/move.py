"""Move model and move hierarchy for creatures."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Move(ABC):
    """Abstract base class representing a move used in battle."""

    def __init__(
        self,
        move_id: str,
        name: str,
        move_type: str,
        category: str,
        power: int,
        accuracy: int,
        pp: int,
        effect: Optional[str] = None,
        effect_chance: int = 0,
        current_pp: Optional[int] = None,
    ):
        self.id = move_id
        self.name = name
        self.type = move_type
        self.category = category.lower()  # "physical", "special", "status"
        self.power = power
        self.accuracy = accuracy
        self.max_pp = pp
        self.current_pp = pp if current_pp is None else current_pp
        self.effect = effect
        self.effect_chance = effect_chance

    def can_use(self) -> bool:
        """Check if move has remaining PP."""
        return self.current_pp > 0

    def use(self) -> bool:
        """Expend 1 PP to use this move. Returns True if successfully used."""
        if self.can_use():
            self.current_pp -= 1
            return True
        return False

    def restore_pp(self, amount: Optional[int] = None) -> int:
        """Restore PP up to max_pp. If amount is None, restore fully."""
        if amount is None:
            restored = self.max_pp - self.current_pp
            self.current_pp = self.max_pp
            return restored
        old_pp = self.current_pp
        self.current_pp = min(self.max_pp, self.current_pp + amount)
        return self.current_pp - old_pp

    @abstractmethod
    def is_damaging(self) -> bool:
        """Check if move inflicts direct HP damage."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize move state."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "category": self.category,
            "power": self.power,
            "accuracy": self.accuracy,
            "pp": self.max_pp,
            "current_pp": self.current_pp,
            "effect": self.effect,
            "effect_chance": self.effect_chance,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} ({self.type}) PP:{self.current_pp}/{self.max_pp}>"


class AttackMove(Move):
    """A move that deals damage (Physical or Special)."""

    def is_damaging(self) -> bool:
        return True


class StatusMove(Move):
    """A move that inflicts status, stat changes, or healing."""

    def is_damaging(self) -> bool:
        return False


class MoveFactory:
    """Factory to instantiate Move subclasses from data dictionaries."""

    @staticmethod
    def from_json(data: Dict[str, Any]) -> Move:
        category = data.get("category", "physical").lower()
        if category in ("physical", "special"):
            return AttackMove(
                move_id=data["id"],
                name=data["name"],
                move_type=data["type"],
                category=category,
                power=data.get("power", 0),
                accuracy=data.get("accuracy", 100),
                pp=data.get("pp", 20),
                effect=data.get("effect"),
                effect_chance=data.get("effect_chance", 0),
                current_pp=data.get("current_pp"),
            )
        else:
            return StatusMove(
                move_id=data["id"],
                name=data["name"],
                move_type=data["type"],
                category="status",
                power=data.get("power", 0),
                accuracy=data.get("accuracy", 100),
                pp=data.get("pp", 20),
                effect=data.get("effect"),
                effect_chance=data.get("effect_chance", 0),
                current_pp=data.get("current_pp"),
            )
