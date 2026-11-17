"""Trainer, Party and PC storage."""
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.model.bag import Bag
from src.model.creature import Creature
from src.model.item import Item


class _CreatureCollection:
    """Shared read-only view over a private list of creatures."""

    def __init__(self, creatures: Optional[List[Creature]] = None):
        self._creatures: List[Creature] = list(creatures or [])

    @property
    def creatures(self) -> Tuple[Creature, ...]:
        return tuple(self._creatures)

    @property
    def size(self) -> int:
        return len(self._creatures)

    def __len__(self) -> int:
        return len(self._creatures)

    def __iter__(self) -> Iterator[Creature]:
        return iter(self.creatures)

    def __contains__(self, creature: Creature) -> bool:
        return creature in self._creatures

    def to_dict(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._creatures]


class Party(_CreatureCollection):
    """A trainer's team of up to 6 creatures. The first healthy one fights."""

    MAX_PARTY_SIZE = 6

    def __init__(self, creatures: Optional[List[Creature]] = None):
        if creatures and len(creatures) > self.MAX_PARTY_SIZE:
            raise ValueError(f"A party holds at most {self.MAX_PARTY_SIZE} creatures")
        super().__init__(creatures)

    @property
    def is_full(self) -> bool:
        return len(self._creatures) >= self.MAX_PARTY_SIZE

    def add(self, creature: Creature) -> bool:
        """Add a creature. Returns False if the party is full."""
        if self.is_full:
            return False
        self._creatures.append(creature)
        return True

    def remove(self, index: int) -> Optional[Creature]:
        """Remove and return the creature at ``index``. The last creature can't be removed."""
        if len(self._creatures) > 1 and 0 <= index < len(self._creatures):
            return self._creatures.pop(index)
        return None

    def swap(self, index_a: int, index_b: int) -> bool:
        n = len(self._creatures)
        if 0 <= index_a < n and 0 <= index_b < n:
            self._creatures[index_a], self._creatures[index_b] = (
                self._creatures[index_b], self._creatures[index_a])
            return True
        return False

    def get_active(self) -> Optional[Creature]:
        """The first creature that hasn't fainted, or None."""
        return next((c for c in self._creatures if not c.is_fainted), None)

    @property
    def lead(self) -> Optional[Creature]:
        return self.get_active()

    def all_fainted(self) -> bool:
        return all(c.is_fainted for c in self._creatures)

    def ready_to_evolve(self) -> Tuple[Creature, ...]:
        """Creatures that have reached their evolution level."""
        return tuple(c for c in self._creatures if c.can_evolve())

    def heal_all(self) -> None:
        """Healing-center treatment for the whole party, including fainted creatures."""
        for c in self._creatures:
            c.restore_fully()


class PCBox(_CreatureCollection):
    """Unlimited storage for creatures caught while the party is full."""

    def deposit(self, creature: Creature) -> None:
        self._creatures.append(creature)

    def withdraw(self, index: int) -> Optional[Creature]:
        if 0 <= index < len(self._creatures):
            return self._creatures.pop(index)
        return None


class Trainer:
    """The player (or, later, an NPC trainer): a name, a party, a bag, money and a PC box."""

    def __init__(
        self,
        name: str = "Player",
        party: Optional[Party] = None,
        bag: Optional[Bag] = None,
        money: int = 1000,
        pc: Optional[PCBox] = None,
    ):
        self._name = name
        self._party = party or Party()
        self._bag = bag or Bag()
        self._money = max(0, money)
        self._pc = pc or PCBox()

    @property
    def name(self) -> str:
        return self._name

    def rename(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("A trainer needs a name")
        self._name = name

    @property
    def party(self) -> Party:
        return self._party

    @property
    def bag(self) -> Bag:
        return self._bag

    @property
    def pc(self) -> PCBox:
        return self._pc

    @property
    def money(self) -> int:
        return self._money

    def earn(self, amount: int) -> None:
        self._money += max(0, amount)

    def spend(self, amount: int) -> bool:
        """Pay ``amount``. Returns False (and pays nothing) if there isn't enough."""
        if amount < 0 or amount > self._money:
            return False
        self._money -= amount
        return True

    def black_out(self) -> int:
        """All creatures fainted: lose half the money and get healed. Returns money lost."""
        lost = self._money // 2
        self._money -= lost
        self._party.heal_all()
        return lost

    def receive_creature(self, creature: Creature) -> str:
        """Put a new creature in the party, or the PC box if the party is full.

        Returns where it went: "party" or "pc".
        """
        if self._party.add(creature):
            return "party"
        self._pc.deposit(creature)
        return "pc"

    # Convenience wrappers around the bag ------------------------------
    def add_item(self, item: Item, quantity: int = 1) -> None:
        self._bag.add(item, quantity)

    def has_item(self, item_id: str) -> bool:
        return self._bag.has(item_id)

    def get_item(self, item_id: str) -> Optional[Item]:
        return self._bag.get(item_id)

    def use_item(self, item_id: str, target: Creature) -> str:
        return self._bag.use(item_id, target)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "party": self._party.to_dict(),
            "inventory": self._bag.to_list(),
            "money": self._money,
            "pc": self._pc.to_dict(),
        }
