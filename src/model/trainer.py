"""Trainer and Party models."""
from typing import List, Dict, Optional, Any
from src.model.creature import Creature
from src.model.item import Item


class Party:
    """Manages a trainer's active team of up to 6 creatures."""

    MAX_PARTY_SIZE = 6

    def __init__(self, creatures: Optional[List[Creature]] = None):
        self.creatures: List[Creature] = creatures or []

    @property
    def size(self) -> int:
        return len(self.creatures)

    @property
    def is_full(self) -> bool:
        return len(self.creatures) >= self.MAX_PARTY_SIZE

    def add(self, creature: Creature) -> bool:
        """Add creature to party. Returns False if party is full."""
        if self.is_full:
            return False
        self.creatures.append(creature)
        return True

    def remove(self, index: int) -> Optional[Creature]:
        """Remove and return creature at given index."""
        if 0 <= index < len(self.creatures):
            return self.creatures.pop(index)
        return None

    def swap(self, index_a: int, index_b: int) -> bool:
        """Swap positions of two creatures in party."""
        if 0 <= index_a < len(self.creatures) and 0 <= index_b < len(self.creatures):
            self.creatures[index_a], self.creatures[index_b] = (
                self.creatures[index_b],
                self.creatures[index_a],
            )
            return True
        return False

    def get_active(self) -> Optional[Creature]:
        """Return the lead non-fainted creature in the party."""
        for c in self.creatures:
            if not c.is_fainted:
                return c
        return None

    def all_fainted(self) -> bool:
        """Return True if all creatures in the party are fainted."""
        return len(self.creatures) == 0 or all(c.is_fainted for c in self.creatures)

    def heal_all(self) -> None:
        """Restore all creatures to full HP and cure status conditions."""
        for c in self.creatures:
            c.heal(c.max_hp)
            c.cure_status()

    def to_dict(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.creatures]


class Trainer:
    """Represents the player or an NPC trainer."""

    def __init__(
        self,
        name: str = "Red",
        party: Optional[Party] = None,
        inventory: Optional[Dict[str, Item]] = None,
        money: int = 1000,
    ):
        self.name = name
        self.party = party or Party()
        self.inventory: Dict[str, Item] = inventory or {}
        self.money = money

    def add_item(self, item: Item, quantity: int = 1) -> None:
        """Add item or increase quantity in inventory."""
        if item.id in self.inventory:
            self.inventory[item.id].quantity += quantity
        else:
            item.quantity = quantity
            self.inventory[item.id] = item

    def has_item(self, item_id: str) -> bool:
        return item_id in self.inventory and self.inventory[item_id].quantity > 0

    def get_item(self, item_id: str) -> Optional[Item]:
        return self.inventory.get(item_id)

    def use_item(self, item_id: str, target: Creature) -> str:
        """Apply an item to a creature from inventory."""
        item = self.get_item(item_id)
        if not item or not item.has_stock():
            return f"You don't have any {item_id}!"

        result = item.use(target)
        if item.quantity <= 0:
            del self.inventory[item_id]
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "party": self.party.to_dict(),
            "inventory": [item.to_dict() for item in self.inventory.values()],
            "money": self.money,
        }
