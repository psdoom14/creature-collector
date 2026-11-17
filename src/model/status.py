"""Status conditions (burn, poison, paralysis, sleep) as a class hierarchy.

Each condition decides for itself who it can affect, whether its holder can act,
what happens at the end of a turn and how it changes speed and catch odds.
``Battle`` just calls these methods, so it never needs ``if status == "sleep"``.
"""
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Tuple, Type
from src.model.errors import GameDataError

if TYPE_CHECKING:
    from src.model.creature import Creature


class StatusCondition(ABC):
    """Abstract base for a lasting status condition on a creature."""

    #: Short id used in data files and saves ("burn", "sleep", ...).
    key: str = ""
    #: Creature types that can never get this condition.
    immune_types: frozenset = frozenset()
    #: Multiplier applied to catch chance while the target has this condition.
    catch_bonus: float = 1.5

    _registry: Dict[str, Type["StatusCondition"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.key:
            StatusCondition._registry[cls.key] = cls

    @classmethod
    def create(cls, key: str) -> "StatusCondition":
        """Factory: build the condition registered under ``key``."""
        try:
            return cls._registry[key.lower()]()
        except KeyError:
            raise GameDataError(f"Unknown status condition '{key}'") from None

    @classmethod
    def known_keys(cls) -> Tuple[str, ...]:
        return tuple(cls._registry)

    def can_afflict(self, creature: "Creature") -> bool:
        """Whether this condition can be given to ``creature`` (type immunities)."""
        return not (set(creature.types) & self.immune_types)

    @abstractmethod
    def applied_message(self, name: str) -> str:
        """Text shown when a creature gets this condition."""

    def before_move(self, creature: "Creature") -> Tuple[bool, Optional[str]]:
        """Called before the holder moves. Returns (can_act, message or None)."""
        return True, None

    def on_turn_end(self, creature: "Creature") -> Tuple[int, Optional[str]]:
        """Called at end of turn. Returns (damage to deal, message or None)."""
        return 0, None

    def modify_speed(self, speed: int) -> int:
        return speed

    @property
    def label(self) -> str:
        """Three-letter badge text for the HUD (BRN, PSN, ...)."""
        return self.key[:3].upper()

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.key == other.lower()
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class _ChipDamageStatus(StatusCondition, ABC):
    """Shared behaviour for conditions that hurt 1/16 max HP every turn."""
    damage_verb: str = ""

    def on_turn_end(self, creature: "Creature") -> Tuple[int, Optional[str]]:
        return max(1, creature.max_hp // 16), f"{creature.name} was hurt by {self.damage_verb}!"


class Burn(_ChipDamageStatus):
    key = "burn"
    immune_types = frozenset({"Fire"})
    damage_verb = "its burn"

    def applied_message(self, name: str) -> str:
        return f"{name} was burned!"

    @property
    def label(self) -> str:
        return "BRN"


class Poison(_ChipDamageStatus):
    key = "poison"
    immune_types = frozenset({"Poison"})
    damage_verb = "poison"

    def applied_message(self, name: str) -> str:
        return f"{name} was poisoned!"

    @property
    def label(self) -> str:
        return "PSN"


class Paralysis(StatusCondition):
    key = "paralyze"
    immune_types = frozenset({"Electric"})
    FULL_PARALYSIS_CHANCE = 0.25

    def applied_message(self, name: str) -> str:
        return f"{name} is paralyzed! It may be unable to move!"

    def before_move(self, creature: "Creature") -> Tuple[bool, Optional[str]]:
        if random.random() < self.FULL_PARALYSIS_CHANCE:
            return False, f"{creature.name} is fully paralyzed! It can't move!"
        return True, None

    def modify_speed(self, speed: int) -> int:
        return max(1, speed // 2)

    @property
    def label(self) -> str:
        return "PAR"


class Sleep(StatusCondition):
    key = "sleep"
    catch_bonus = 2.0
    MIN_TURNS, MAX_TURNS = 1, 3

    def __init__(self, turns: Optional[int] = None):
        self._turns_left = turns if turns is not None else random.randint(self.MIN_TURNS, self.MAX_TURNS)

    @property
    def turns_left(self) -> int:
        return self._turns_left

    def applied_message(self, name: str) -> str:
        return f"{name} fell asleep!"

    def before_move(self, creature: "Creature") -> Tuple[bool, Optional[str]]:
        if self._turns_left > 0:
            self._turns_left -= 1
            return False, f"{creature.name} is fast asleep!"
        creature.cure_status()
        return True, f"{creature.name} woke up!"

    @property
    def label(self) -> str:
        return "SLP"
