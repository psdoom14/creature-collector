"""Item model and subclass hierarchy."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Union
from src.model.creature import Creature


class Item(ABC):
    """Abstract base class for all consumable inventory items."""

    def __init__(
        self,
        item_id: str,
        name: str,
        item_type: str,
        effect_value: Union[int, float, str],
        description: str,
        quantity: int = 1,
    ):
        self.id = item_id
        self.name = name
        self.item_type = item_type
        self.effect_value = effect_value
        self.description = description
        self.quantity = quantity

    def has_stock(self) -> bool:
        return self.quantity > 0

    def consume(self) -> bool:
        if self.has_stock():
            self.quantity -= 1
            return True
        return False

    @abstractmethod
    def can_use(self, target: Creature) -> bool:
        """Check if this item can be applied to target creature."""
        pass

    @abstractmethod
    def use(self, target: Creature) -> str:
        """Apply item to creature and return human-readable outcome message."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.item_type,
            "effect_value": self.effect_value,
            "description": self.description,
            "quantity": self.quantity,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} x{self.quantity}>"


class HealingItem(Item):
    """Restores HP to an active, unfainted creature."""

    def can_use(self, target: Creature) -> bool:
        return (not target.is_fainted) and (target.current_hp < target.max_hp)

    def use(self, target: Creature) -> str:
        if not self.can_use(target):
            return f"It will have no effect on {target.name}."
        if not self.consume():
            return f"No {self.name} remaining!"

        healed = target.heal(int(self.effect_value))
        return f"Restored {healed} HP to {target.name}!"


class StatusCureItem(Item):
    """Cures a specific status condition on an unfainted creature."""

    def can_use(self, target: Creature) -> bool:
        if target.is_fainted or not target.status_effect:
            return False
        return target.status_effect == str(self.effect_value).lower()

    def use(self, target: Creature) -> str:
        if not self.can_use(target):
            return f"It will have no effect on {target.name}."
        if not self.consume():
            return f"No {self.name} remaining!"

        cured = target.cure_status()
        return f"{target.name}'s {cured} condition was cured!"


class ReviveItem(Item):
    """Revives a fainted creature with a fraction of its max HP."""

    def can_use(self, target: Creature) -> bool:
        return target.is_fainted

    def use(self, target: Creature) -> str:
        if not self.can_use(target):
            return f"{target.name} is not fainted!"
        if not self.consume():
            return f"No {self.name} remaining!"

        fraction = float(self.effect_value)
        healed = target.revive(fraction)
        return f"{target.name} was revived with {healed} HP!"


class CatchBall(Item):
    """Device used to capture wild creatures in combat."""

    @property
    def ball_multiplier(self) -> float:
        return float(self.effect_value)

    def can_use(self, target: Creature) -> bool:
        return not target.is_fainted

    def calc_catch_chance(self, creature: Creature) -> float:
        """
        Calculates catch probability based on HP percent, catch rate, and ball multiplier.
        Returns a float between 0.05 and 1.0.
        """
        max_hp = creature.max_hp
        curr_hp = max(1, creature.current_hp)
        rate = creature.catch_rate

        # Classic modified formula
        numerator = (3 * max_hp - 2 * curr_hp) * rate * self.ball_multiplier
        denominator = 3 * max_hp * 255.0
        chance = numerator / denominator

        # Status effect bonus
        if creature.status_effect in ("sleep", "freeze"):
            chance *= 2.0
        elif creature.status_effect in ("paralyze", "poison", "burn"):
            chance *= 1.5

        return max(0.05, min(1.0, chance))

    def use(self, target: Creature) -> str:
        if not self.consume():
            return f"Out of {self.name}s!"
        return f"Threw a {self.name} at {target.name}!"


class ItemFactory:
    """Factory to instantiate concrete Item subclasses."""

    @staticmethod
    def from_json(data: Dict[str, Any], quantity: int = 1) -> Item:
        item_type = data.get("type", "healing").lower()
        item_id = data["id"]
        name = data["name"]
        val = data.get("effect_value", 0)
        desc = data.get("description", "")
        qty = data.get("quantity", quantity)

        if item_type == "healing":
            return HealingItem(item_id, name, item_type, val, desc, qty)
        elif item_type == "status_cure":
            return StatusCureItem(item_id, name, item_type, val, desc, qty)
        elif item_type == "revive":
            return ReviveItem(item_id, name, item_type, val, desc, qty)
        elif item_type == "catch":
            return CatchBall(item_id, name, item_type, val, desc, qty)
        else:
            return HealingItem(item_id, name, item_type, val, desc, qty)
