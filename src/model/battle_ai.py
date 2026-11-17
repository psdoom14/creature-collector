"""How opponents pick their moves.

    BattleAI (abstract)
    └── RandomAI     picks any move with PP left (wild creatures)

A smarter AI for gym leaders can be added later as another subclass without
touching ``Battle``.
"""
import random
from abc import ABC, abstractmethod

from src.model.creature import Creature
from src.model.move import Move, MoveFactory


class BattleAI(ABC):
    """Strategy for choosing an opponent's move each turn."""

    def choose_move(self, creature: Creature, target: Creature) -> Move:
        """Pick a move for ``creature`` to use on ``target``. Falls back to Struggle."""
        usable = [m for m in creature.moves if m.can_use()]
        if not usable:
            return MoveFactory.struggle()
        return self._pick(usable, creature, target)

    @abstractmethod
    def _pick(self, usable: list, creature: Creature, target: Creature) -> Move:
        """Choose one of ``usable`` (never empty)."""


class RandomAI(BattleAI):
    """Picks a random usable move."""

    def _pick(self, usable: list, creature: Creature, target: Creature) -> Move:
        return random.choice(usable)
