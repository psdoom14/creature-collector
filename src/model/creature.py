"""The Creature model.

All mutable state (HP, level, XP, status, moves, stat stages) is private. Other
code can read it through properties but can only change it through methods such
as ``take_damage()``, ``heal()``, ``gain_xp()`` and ``learn_move()``, which
enforce the rules (HP never below 0 or above max, at most 4 moves, ...).
"""
import itertools
from typing import Any, Dict, List, Optional, Tuple, Union

from src.model.move import Move
from src.model.status import StatusCondition

MAX_LEVEL = 100
MAX_MOVES = 4
STAGE_LIMIT = 6
BATTLE_STATS = ("attack", "defense", "sp_attack", "sp_defense", "speed")


def exp_for_level(level: int) -> int:
    """Total XP needed to reach ``level`` (Medium-Fast curve: level^3)."""
    return level ** 3


class Creature:
    """A single creature: species data plus its own level, HP, moves and status."""

    _uid_counter = itertools.count(1)

    def __init__(
        self,
        species_id: int,
        name: str,
        types: List[str],
        base_stats: Dict[str, int],
        level: int = 5,
        xp: Optional[int] = None,
        moves: Optional[List[Move]] = None,
        learnable_moves: Optional[List[Dict[str, Any]]] = None,
        evolution: Optional[Dict[str, Any]] = None,
        catch_rate: int = 45,
        base_xp: int = 60,
        sprite_front: str = "",
        sprite_back: str = "",
        current_hp: Optional[int] = None,
        status_effect: Optional[Union[str, StatusCondition]] = None,
    ):
        self._uid = next(Creature._uid_counter)
        self._set_species(species_id, name, types, base_stats, learnable_moves, evolution,
                          catch_rate, base_xp, sprite_front, sprite_back)
        self._level = max(1, min(MAX_LEVEL, level))
        self._xp = exp_for_level(self._level) if xp is None else xp
        self._stat_stages: Dict[str, int] = {s: 0 for s in BATTLE_STATS}
        self._stats: Dict[str, int] = {}
        self._recalculate_stats()
        self._hp = self.max_hp if current_hp is None else max(0, min(current_hp, self.max_hp))
        self._moves: List[Move] = list(moves or [])[:MAX_MOVES]
        self._status: Optional[StatusCondition] = None
        if status_effect and not self.is_fainted:
            self._status = (status_effect if isinstance(status_effect, StatusCondition)
                            else StatusCondition.create(status_effect))

    def _set_species(self, species_id, name, types, base_stats, learnable_moves, evolution,
                     catch_rate, base_xp, sprite_front, sprite_back) -> None:
        self._species_id = species_id
        self._name = name
        self._types: Tuple[str, ...] = tuple(t.capitalize() for t in types) or ("Normal",)
        self._base_stats = dict(base_stats)
        self._learnable_moves = [dict(m) for m in (learnable_moves or [])]
        self._evolution = dict(evolution) if evolution else None
        self._catch_rate = catch_rate
        self._base_xp = base_xp
        self._sprite_front = sprite_front
        self._sprite_back = sprite_back

    # ------------------------------------------------------------------
    # Read-only species data
    # ------------------------------------------------------------------
    @property
    def uid(self) -> int:
        """Unique id for this individual creature (two wild Rattata have different uids)."""
        return self._uid

    @property
    def species_id(self) -> int:
        return self._species_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def types(self) -> Tuple[str, ...]:
        return self._types

    @property
    def primary_type(self) -> str:
        return self._types[0]

    @property
    def base_stats(self) -> Dict[str, int]:
        return dict(self._base_stats)

    @property
    def learnable_moves(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._learnable_moves]

    @property
    def evolution(self) -> Optional[Dict[str, Any]]:
        return dict(self._evolution) if self._evolution else None

    @property
    def catch_rate(self) -> int:
        return self._catch_rate

    @property
    def base_xp(self) -> int:
        return self._base_xp

    @property
    def sprite_front(self) -> str:
        return self._sprite_front

    @property
    def sprite_back(self) -> str:
        return self._sprite_back

    # ------------------------------------------------------------------
    # Read-only individual state
    # ------------------------------------------------------------------
    @property
    def level(self) -> int:
        return self._level

    @property
    def xp(self) -> int:
        return self._xp

    @property
    def xp_progress(self) -> float:
        """Fraction (0.0-1.0) of the way from this level to the next."""
        if self._level >= MAX_LEVEL:
            return 1.0
        start, end = exp_for_level(self._level), exp_for_level(self._level + 1)
        return max(0.0, min(1.0, (self._xp - start) / max(1, end - start)))

    @property
    def current_hp(self) -> int:
        return self._hp

    @property
    def max_hp(self) -> int:
        return self._stats["hp"]

    @property
    def is_fainted(self) -> bool:
        return self._hp <= 0

    @property
    def moves(self) -> Tuple[Move, ...]:
        return tuple(self._moves)

    @property
    def status(self) -> Optional[StatusCondition]:
        return self._status

    @property
    def status_effect(self) -> Optional[str]:
        """The status key ("burn", "sleep", ...) or None."""
        return self._status.key if self._status else None

    def stat_stage(self, stat_name: str) -> int:
        return self._stat_stages.get(stat_name, 0)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    @property
    def attack(self) -> int:
        return self._staged_stat("attack")

    @property
    def defense(self) -> int:
        return self._staged_stat("defense")

    @property
    def sp_attack(self) -> int:
        return self._staged_stat("sp_attack")

    @property
    def sp_defense(self) -> int:
        return self._staged_stat("sp_defense")

    @property
    def speed(self) -> int:
        spd = self._staged_stat("speed")
        return self._status.modify_speed(spd) if self._status else spd

    def _recalculate_stats(self) -> None:
        base_hp = self._base_stats.get("hp", 45)
        self._stats["hp"] = int((base_hp * 2 * self._level) / 100) + self._level + 10
        for stat in BATTLE_STATS:
            base_val = self._base_stats.get(stat, 50)
            self._stats[stat] = int((base_val * 2 * self._level) / 100) + 5

    def _staged_stat(self, stat_name: str) -> int:
        base = self._stats.get(stat_name, 10)
        stage = self._stat_stages.get(stat_name, 0)
        multiplier = (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)
        return max(1, int(base * multiplier))

    def reset_battle_stages(self) -> None:
        """Clear temporary battle buffs/debuffs."""
        for k in self._stat_stages:
            self._stat_stages[k] = 0

    def modify_stat_stage(self, stat_name: str, change: int) -> int:
        """Shift a battle stat by ``change`` stages (clamped to ±6). Returns the actual shift."""
        if stat_name not in self._stat_stages:
            return 0
        old = self._stat_stages[stat_name]
        self._stat_stages[stat_name] = max(-STAGE_LIMIT, min(STAGE_LIMIT, old + change))
        return self._stat_stages[stat_name] - old

    # ------------------------------------------------------------------
    # HP
    # ------------------------------------------------------------------
    def take_damage(self, amount: int) -> int:
        """Lose HP (at least 1). Returns HP actually lost."""
        loss = min(self._hp, max(1, amount))
        self._hp -= loss
        if self._hp == 0:
            self._status = None
        return loss

    def heal(self, amount: int) -> int:
        """Restore HP up to max. Does nothing to a fainted creature. Returns HP restored."""
        if self.is_fainted or amount <= 0:
            return 0
        old = self._hp
        self._hp = min(self.max_hp, self._hp + amount)
        return self._hp - old

    def revive(self, hp_fraction: float = 0.5) -> int:
        """Bring a fainted creature back with a fraction of max HP. Returns HP restored."""
        if not self.is_fainted:
            return 0
        self._hp = max(1, int(self.max_hp * hp_fraction))
        self._status = None
        return self._hp

    def restore_fully(self) -> None:
        """Healing-center treatment: full HP (even if fainted), no status, full PP."""
        self._hp = self.max_hp
        self._status = None
        self.reset_battle_stages()
        for move in self._moves:
            move.restore_pp()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def apply_status(self, status: Union[str, StatusCondition]) -> bool:
        """Try to give this creature a status. Fails if fainted, already afflicted or immune."""
        if self.is_fainted or self._status is not None:
            return False
        condition = status if isinstance(status, StatusCondition) else StatusCondition.create(status)
        if not condition.can_afflict(self):
            return False
        self._status = condition
        return True

    def cure_status(self) -> Optional[str]:
        """Remove any status. Returns the key of the cured status, or None."""
        cured = self.status_effect
        self._status = None
        return cured

    # ------------------------------------------------------------------
    # Experience, moves, evolution
    # ------------------------------------------------------------------
    def gain_xp(self, amount: int) -> Dict[str, Any]:
        """Add XP, levelling up as many times as earned. Returns a summary."""
        self._xp += max(0, amount)
        initial_level = self._level
        while self._level < MAX_LEVEL and self._xp >= exp_for_level(self._level + 1):
            old_max = self.max_hp
            self._level += 1
            self._recalculate_stats()
            if not self.is_fainted:
                self._hp += self.max_hp - old_max

        unlocked = [m["move_id"] for m in self._learnable_moves
                    if initial_level < m["level"] <= self._level]
        return {
            "leveled_up": self._level > initial_level,
            "old_level": initial_level,
            "new_level": self._level,
            "can_evolve": self.can_evolve(),
            "unlocked_moves": unlocked,
        }

    def knows_move(self, move_id: str) -> bool:
        return any(m.id == move_id for m in self._moves)

    def learn_move(self, new_move: Move, slot: Optional[int] = None) -> bool:
        """Add a move (max 4). With 4 known, ``slot`` picks which one to replace."""
        if self.knows_move(new_move.id):
            return False
        if len(self._moves) < MAX_MOVES:
            self._moves.append(new_move)
            return True
        if slot is not None and 0 <= slot < len(self._moves):
            self._moves[slot] = new_move
            return True
        return False

    @property
    def evolves_into(self) -> Optional[int]:
        """Species id this creature evolves into, or None."""
        return self._evolution.get("into") if self._evolution else None

    def can_evolve(self) -> bool:
        if not self._evolution:
            return False
        return self._level >= self._evolution.get("level", MAX_LEVEL + 1)

    def evolve(self, new_species_data: Dict[str, Any]) -> "Creature":
        """Become the evolved species in place, keeping level, XP, moves, status and damage taken.

        Returns ``self`` so the same object stays in the party.
        """
        damage_taken = self.max_hp - self._hp
        d = new_species_data
        self._set_species(
            d["id"], d["name"], d.get("types", ["Normal"]), d["base_stats"],
            d.get("learnable_moves", []), d.get("evolution"), d.get("catch_rate", 45),
            d.get("base_xp", 60), d.get("sprite_front", ""), d.get("sprite_back", ""),
        )
        self._recalculate_stats()
        if not self.is_fainted:
            self._hp = max(1, self.max_hp - damage_taken)
        return self

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "species_id": self._species_id,
            "name": self._name,
            "types": list(self._types),
            "level": self._level,
            "xp": self._xp,
            "current_hp": self._hp,
            "status_effect": self.status_effect,
            "moves": [m.to_dict() for m in self._moves],
            "base_stats": dict(self._base_stats),
            "learnable_moves": self.learnable_moves,
            "evolution": self.evolution,
            "catch_rate": self._catch_rate,
            "base_xp": self._base_xp,
            "sprite_front": self._sprite_front,
            "sprite_back": self._sprite_back,
        }

    def __repr__(self) -> str:
        return f"<Creature {self._name} Lv.{self._level} HP:{self._hp}/{self.max_hp}>"


class CreatureFactory:
    """Factory that builds a Creature from a creatures.json species entry."""

    @staticmethod
    def create(
        species_data: Dict[str, Any],
        level: int = 5,
        xp: Optional[int] = None,
        moves: Optional[List[Move]] = None,
        current_hp: Optional[int] = None,
        status_effect: Optional[str] = None,
    ) -> Creature:
        return Creature(
            species_id=species_data["id"],
            name=species_data["name"],
            types=species_data.get("types", ["Normal"]),
            base_stats=species_data["base_stats"],
            level=level,
            xp=xp,
            moves=moves,
            learnable_moves=species_data.get("learnable_moves", []),
            evolution=species_data.get("evolution"),
            catch_rate=species_data.get("catch_rate", 45),
            base_xp=species_data.get("base_xp", 60),
            sprite_front=species_data.get("sprite_front", ""),
            sprite_back=species_data.get("sprite_back", ""),
            current_hp=current_hp,
            status_effect=status_effect,
        )
