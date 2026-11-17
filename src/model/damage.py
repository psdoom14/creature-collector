"""The damage formula, kept in one small class (Single Responsibility).

``Battle`` decides *when* moves happen; ``DamageCalculator`` decides *how much*
they hurt. The random source can be injected, which makes the formula easy to
test with fixed rolls.
"""
import random
from dataclasses import dataclass
from typing import Optional

from src.model.creature import Creature
from src.model.move import Move
from src.model.type_chart import TypeChart

CRIT_CHANCE = 0.0625
CRIT_MULTIPLIER = 1.5
STAB_MULTIPLIER = 1.5          # same-type attack bonus
VARIANCE = (0.85, 1.0)


@dataclass(frozen=True)
class DamageResult:
    damage: int
    multiplier: float          # type effectiveness (0, 0.25 ... 4)
    is_crit: bool
    hit: bool

    @property
    def no_effect(self) -> bool:
        return self.hit and self.multiplier == 0.0


class DamageCalculator:
    """Accuracy, critical hits, same-type bonus, type effectiveness and random variance."""

    def __init__(self, type_chart: TypeChart, rng: Optional[random.Random] = None):
        self._chart = type_chart
        self._rng = rng or random

    def calculate(self, attacker: Creature, defender: Creature, move: Move) -> DamageResult:
        if not move.is_damaging() or move.power <= 0:
            return DamageResult(0, 1.0, False, True)
        if self._rng.randint(1, 100) > move.accuracy:
            return DamageResult(0, 1.0, False, False)

        atk = move.attack_stat(attacker)        # polymorphic: Physical vs Special
        dfn = move.defense_stat(defender)
        is_crit = self._rng.random() < CRIT_CHANCE
        base = ((2 * attacker.level / 5 + 2) * move.power * (atk / max(1, dfn))) / 50 + 2
        stab = STAB_MULTIPLIER if move.type in attacker.types else 1.0
        type_mult = self._chart.get_effectiveness(move.type, list(defender.types))
        crit = CRIT_MULTIPLIER if is_crit else 1.0
        damage = int(base * stab * type_mult * crit * self._rng.uniform(*VARIANCE))
        damage = max(1, damage) if type_mult > 0 else 0
        return DamageResult(damage, type_mult, is_crit, True)
