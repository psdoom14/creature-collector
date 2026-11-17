"""The player's bag: owns all items and keeps their stock consistent."""
from typing import Dict, Iterator, List, Optional, Tuple

from src.model.creature import Creature
from src.model.item import Item


class Bag:
    """Holds items by id. Empty stacks are removed automatically."""

    def __init__(self, items: Optional[List[Item]] = None):
        self._items: Dict[str, Item] = {}
        for item in items or []:
            self.add(item, item.quantity)

    @property
    def items(self) -> Tuple[Item, ...]:
        """All items, in the order they were first added."""
        return tuple(self._items.values())

    def __iter__(self) -> Iterator[Item]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        return self.has(item_id)

    def add(self, item: Item, quantity: int = 1) -> None:
        """Add ``quantity`` of ``item``, stacking onto an existing entry with the same id."""
        if quantity <= 0:
            return
        if item.id in self._items:
            self._items[item.id].add_stock(quantity)
        else:
            if item.quantity != quantity:
                # Normalise the stack to exactly `quantity`.
                while item.consume():
                    pass
                item.add_stock(quantity)
            self._items[item.id] = item

    def get(self, item_id: str) -> Optional[Item]:
        return self._items.get(item_id)

    def has(self, item_id: str) -> bool:
        item = self._items.get(item_id)
        return item is not None and item.has_stock()

    def remove(self, item_id: str, quantity: int = 1) -> int:
        """Take up to ``quantity`` of an item out of the bag. Returns how many were removed."""
        item = self._items.get(item_id)
        removed = 0
        while item is not None and removed < quantity and item.consume():
            removed += 1
        self.remove_empty()
        return removed

    def remove_empty(self) -> None:
        """Drop stacks that have run out."""
        for item_id in [i for i, it in self._items.items() if not it.has_stock()]:
            del self._items[item_id]

    def use(self, item_id: str, target: Creature) -> str:
        """Use one item on ``target`` outside battle. Returns a message."""
        item = self.get(item_id)
        if item is None or not item.has_stock():
            return f"You don't have any {item_id}!"
        message = item.use(target)
        self.remove_empty()
        return message

    def to_list(self) -> List[dict]:
        return [item.to_dict() for item in self._items.values()]
