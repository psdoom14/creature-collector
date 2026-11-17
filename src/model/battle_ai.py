"""How opponents pick their moves.

    BattleAI (abstract)
    ├── RandomAI     picks any move with PP left (wild creatures, most trainers)
    └── SmartAI      picks the move expected to hurt the most (rival, gym leaders)
"""
import random
from abc import ABC, abstractmethod

from src.model.creature import Creature
from src.model.move import Move, MoveFactory
from src.model.type_chart import TypeChart


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


class SmartAI(BattleAI):
    """Scores every usable move and picks the best.

    Damaging moves: power x accuracy x same-type bonus x type effectiveness.
    Status moves: each MoveEffect scores itself (``effect.ai_score()``), so a
    heal is worth more when hurt and a status is worthless on an already-afflicted target.
    A small random factor keeps it from being completely predictable.
    """

    def __init__(self, type_chart: TypeChart, randomness: float = 0.1):
        self._chart = type_chart
        self._randomness = randomness

    def score(self, move: Move, creature: Creature, target: Creature) -> float:
        if move.is_damaging():
            stab = 1.5 if move.type in creature.types else 1.0
            effectiveness = self._chart.get_effectiveness(move.type, list(target.types))
            return move.power * (move.accuracy / 100) * stab * effectiveness
        return move.effect.ai_score(creature, target) if move.effect else 1.0

    def _pick(self, usable: list, creature: Creature, target: Creature) -> Move:
        def noisy(move: Move) -> float:
            return self.score(move, creature, target) * (1 + random.uniform(0, self._randomness))
        return max(usable, key=noisy)
