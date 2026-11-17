"""Secondary move effects (inflict a status, heal the user, change a stat).

Each effect is its own class with an ``apply()`` method, replacing the old
string ``if/elif`` chain inside ``Battle``.
"""
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from src.model.events import BattleEvent, EventType
from src.model.status import StatusCondition

if TYPE_CHECKING:
    from src.model.creature import Creature


class MoveEffect(ABC):
    """Abstract base for something a move does besides direct damage."""

    def __init__(self, key: str, chance: int = 100):
        self._key = key
        self._chance = chance

    @property
    def key(self) -> str:
        """The id used in moves.json and saves."""
        return self._key

    @property
    def chance(self) -> int:
        """Percent chance (0-100) that the effect triggers."""
        return self._chance

    def triggers(self) -> bool:
        return random.random() < self._chance / 100.0

    @abstractmethod
    def apply(self, user: "Creature", target: "Creature") -> List[BattleEvent]:
        """Perform the effect. Returns events; an empty list means nothing happened."""

    @staticmethod
    def from_data(key: Optional[str], chance: int = 0) -> Optional["MoveEffect"]:
        """Factory: build the right effect for a moves.json ``effect`` string."""
        if not key:
            return None
        key = key.lower()
        if key in StatusCondition.known_keys():
            return InflictStatus(key, chance)
        if key == "heal":
            return HealUser(key, chance)
        if key.startswith("stat_lower_"):
            return ChangeStat(key, chance, stat=key[len("stat_lower_"):], stages=-1)
        if key.startswith("stat_raise_"):
            return ChangeStat(key, chance, stat=key[len("stat_raise_"):], stages=+1, on_user=True)
        raise ValueError(f"Unknown move effect '{key}'")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._key} {self._chance}%>"


class InflictStatus(MoveEffect):
    """Gives the target a status condition, unless it is immune or already has one."""

    def apply(self, user: "Creature", target: "Creature") -> List[BattleEvent]:
        status = StatusCondition.create(self.key)
        if not target.apply_status(status):
            return []
        return [BattleEvent(
            EventType.STATUS_APPLIED,
            status.applied_message(target.name),
            {"target": target.name, "status": status.key},
        )]


class HealUser(MoveEffect):
    """Restores half of the user's max HP."""
    FRACTION = 0.5

    def apply(self, user: "Creature", target: "Creature") -> List[BattleEvent]:
        healed = user.heal(int(user.max_hp * self.FRACTION))
        if healed <= 0:
            return []
        return [BattleEvent(
            EventType.HEAL,
            f"{user.name} restored {healed} HP!",
            {"user": user.name, "healed": healed},
        )]


class ChangeStat(MoveEffect):
    """Raises or lowers one battle stat by some stages."""
    STAT_NAMES = {
        "attack": "Attack", "defense": "Defense", "sp_attack": "Sp. Atk",
        "sp_defense": "Sp. Def", "speed": "Speed",
    }

    def __init__(self, key: str, chance: int, stat: str, stages: int, on_user: bool = False):
        super().__init__(key, chance)
        self._stat = stat
        self._stages = stages
        self._on_user = on_user

    def apply(self, user: "Creature", target: "Creature") -> List[BattleEvent]:
        who = user if self._on_user else target
        changed = who.modify_stat_stage(self._stat, self._stages)
        if changed == 0:
            return []
        verb = "rose" if changed > 0 else "fell"
        return [BattleEvent(
            EventType.STAT_CHANGE,
            f"{who.name}'s {self.STAT_NAMES.get(self._stat, self._stat)} {verb}!",
            {"target": who.name, "stat": self._stat, "change": changed},
        )]
