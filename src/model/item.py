"""Items as a class hierarchy.

    Item (abstract)
    ├── HealingItem      restores HP
    ├── StatusCureItem   cures one status condition
    ├── ReviveItem       revives a fainted creature
    └── CatchBall        thrown at wild creatures to catch them

Every item answers ``use(target)`` and ``use_in_battle(battle)`` in its own way,
so callers never need to check which kind of item they hold.
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Union

from src.model.creature import Creature
from src.model.events import BattleEvent, EventType
from src.model.errors import GameDataError, RuleViolation

if TYPE_CHECKING:
    from src.model.battle import Battle


class Item(ABC):
    """Abstract base class for all consumable inventory items."""

    #: The "type" string used for this class in items.json.
    KIND: str = ""

    def __init__(
        self,
        item_id: str,
        name: str,
        effect_value: Union[int, float, str],
        description: str = "",
        quantity: int = 1,
        price: int = 0,
    ):
        self._id = item_id
        self._name = name
        self._effect_value = effect_value
        self._description = description
        self._quantity = max(0, quantity)
        self._price = max(0, int(price))

    # --- read-only data ------------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def item_type(self) -> str:
        return self.KIND

    @property
    def effect_value(self) -> Union[int, float, str]:
        return self._effect_value

    @property
    def description(self) -> str:
        return self._description

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def price(self) -> int:
        """What one costs in a shop (0 means shops don't sell it)."""
        return self._price

    @property
    def sell_price(self) -> int:
        """What a shop pays for one: half the price."""
        return self._price // 2

    # --- stock -----------------------------------------------------------
    def has_stock(self) -> bool:
        return self._quantity > 0

    def add_stock(self, amount: int) -> None:
        if amount < 0:
            raise RuleViolation("Stock can only go down through consume()")
        self._quantity += amount

    def consume(self) -> bool:
        """Use up one of this item. Returns False if none are left."""
        if self.has_stock():
            self._quantity -= 1
            return True
        return False

    # --- polymorphic behaviour ----------------------------------------
    @property
    def usable_in_field(self) -> bool:
        """Whether this item can be used from the bag outside battle."""
        return True

    @abstractmethod
    def can_use(self, target: Creature) -> bool:
        """Whether using this item on ``target`` would do anything."""

    @abstractmethod
    def _apply(self, target: Creature) -> str:
        """Apply the effect (stock already checked). Returns a message."""

    def use(self, target: Creature) -> str:
        """Template method: check, consume one, then apply. Returns a message."""
        if not self.can_use(target):
            return f"It won't have any effect on {target.name}."
        if not self.consume():
            return f"No {self._name} left!"
        return self._apply(target)

    def use_in_battle(self, battle: "Battle") -> List[BattleEvent]:
        """Use this item during a battle. Default: on the player's active creature."""
        target = battle.player_creature
        if target is None or not self.can_use(target):
            name = target.name if target else "anyone"
            return [BattleEvent(EventType.INVALID_ACTION, f"It won't have any effect on {name}.")]
        message = self.use(target)
        return [BattleEvent(EventType.ITEM_USED, message,
                            {"item": self._id, "target": target.name, "target_uid": target.uid,
                             "target_current_hp": target.current_hp, "target_max_hp": target.max_hp})]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._id,
            "name": self._name,
            "type": self.KIND,
            "effect_value": self._effect_value,
            "description": self._description,
            "quantity": self._quantity,
            "price": self._price,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name} x{self._quantity}>"


class HealingItem(Item):
    """Restores a fixed amount of HP."""
    KIND = "healing"

    def can_use(self, target: Creature) -> bool:
        return not target.is_fainted and target.current_hp < target.max_hp

    def _apply(self, target: Creature) -> str:
        healed = target.heal(int(self._effect_value))
        return f"{target.name} recovered {healed} HP!"


class StatusCureItem(Item):
    """Cures the one status condition named by ``effect_value``."""
    KIND = "status_cure"

    def can_use(self, target: Creature) -> bool:
        return not target.is_fainted and target.status_effect == str(self._effect_value).lower()

    def _apply(self, target: Creature) -> str:
        cured = target.cure_status()
        return f"{target.name}'s {cured} was cured!"


class ReviveItem(Item):
    """Revives a fainted creature with a fraction of its max HP."""
    KIND = "revive"

    def can_use(self, target: Creature) -> bool:
        return target.is_fainted

    def _apply(self, target: Creature) -> str:
        healed = target.revive(float(self._effect_value))
        return f"{target.name} was revived with {healed} HP!"


class CatchBall(Item):
    """Thrown at a wild creature to try to catch it."""
    KIND = "catch"

    @property
    def usable_in_field(self) -> bool:
        return False  # balls are only thrown in battle

    @property
    def ball_multiplier(self) -> float:
        return float(self._effect_value)

    def can_use(self, target: Creature) -> bool:
        return not target.is_fainted

    def _apply(self, target: Creature) -> str:
        return f"Threw a {self._name} at {target.name}!"

    def calc_catch_chance(self, creature: Creature) -> float:
        """Catch probability (0.05-1.0) from HP left, catch rate, ball and status."""
        max_hp = creature.max_hp
        curr_hp = max(1, creature.current_hp)
        numerator = (3 * max_hp - 2 * curr_hp) * creature.catch_rate * self.ball_multiplier
        chance = numerator / (3 * max_hp * 255.0)
        if creature.status:
            chance *= creature.status.catch_bonus
        return max(0.05, min(1.0, chance))

    def use_in_battle(self, battle: "Battle") -> List[BattleEvent]:
        """Overrides the default: a ball is thrown at the opponent, not used on your creature."""
        return battle.throw_ball(self)


class ItemFactory:
    """Factory that builds the right Item subclass from an items.json entry."""

    _CLASSES = {cls.KIND: cls for cls in (HealingItem, StatusCureItem, ReviveItem, CatchBall)}

    @classmethod
    def from_json(cls, data: Dict[str, Any], quantity: int = 1) -> Item:
        kind = data.get("type", "healing").lower()
        item_cls = cls._CLASSES.get(kind)
        if item_cls is None:
            raise GameDataError(f"Unknown item type '{kind}' for item '{data.get('id')}'")
        return item_cls(
            item_id=data["id"],
            name=data["name"],
            effect_value=data.get("effect_value", 0),
            description=data.get("description", ""),
            quantity=data.get("quantity", quantity),
            price=data.get("price", 0),
        )
