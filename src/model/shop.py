"""A shop: buying and selling items for money.

The shop doesn't know where items come from. It is given an ``item_source`` (any
function that builds an Item from its id, normally ``DataLoader.get_item``), so it
works the same with the real data files or with a few items made up in a test.
"""
from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

from src.model.errors import RuleViolation
from src.model.item import Item
from src.model.trainer import Trainer

ItemSource = Callable[[str, int], Item]

MAX_PER_PURCHASE = 99


@dataclass(frozen=True)
class ShopResult:
    """What happened when the player tried to buy or sell."""
    success: bool
    message: str


class Shop:
    """Sells the items in its stock at their price, and buys any priced item back at half."""

    def __init__(self, stock: Sequence[str], item_source: ItemSource):
        self._item_source = item_source
        catalog = [item_source(item_id, 1) for item_id in stock]
        unpriced = [item.id for item in catalog if item.price <= 0]
        if unpriced:
            raise RuleViolation(f"These items have no price, so a shop can't sell them: {unpriced}")
        self._catalog: Tuple[Item, ...] = tuple(catalog)

    @property
    def catalog(self) -> Tuple[Item, ...]:
        """One sample of each item for sale (for names, prices and descriptions)."""
        return self._catalog

    def sells(self, item_id: str) -> bool:
        return any(item.id == item_id for item in self._catalog)

    def price_of(self, item_id: str) -> int:
        for item in self._catalog:
            if item.id == item_id:
                return item.price
        raise RuleViolation(f"This shop doesn't sell '{item_id}'")

    def max_affordable(self, trainer: Trainer, item_id: str) -> int:
        """How many the trainer can pay for (at most MAX_PER_PURCHASE)."""
        return min(MAX_PER_PURCHASE, trainer.money // self.price_of(item_id))

    def buy(self, trainer: Trainer, item_id: str, quantity: int) -> ShopResult:
        if quantity < 1:
            raise RuleViolation("Buy at least one item")
        price = self.price_of(item_id)
        total = price * quantity
        if not trainer.spend(total):
            return ShopResult(False, "You don't have enough money.")
        item = self._item_source(item_id, quantity)
        trainer.add_item(item, quantity)
        return ShopResult(True, f"You bought {item.name} x{quantity} for ${total}.")

    def sell_price_of(self, item_id: str) -> int:
        """What the shop pays for one (half its price; 0 for unpriced items like key gifts)."""
        return self._item_source(item_id, 1).sell_price

    def sell(self, trainer: Trainer, item_id: str, quantity: int) -> ShopResult:
        if quantity < 1:
            raise RuleViolation("Sell at least one item")
        each = self.sell_price_of(item_id)
        item = trainer.get_item(item_id)
        name = item.name if item else item_id
        if each <= 0:
            return ShopResult(False, f"I'm sorry, I can't buy the {name}.")
        removed = trainer.bag.remove(item_id, quantity)
        if removed == 0:
            return ShopResult(False, f"You don't have any {name}.")
        trainer.earn(each * removed)
        return ShopResult(True, f"You sold {name} x{removed} for ${each * removed}.")
