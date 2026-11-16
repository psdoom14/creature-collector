"""Creature model and type-specific subclasses."""
from typing import List, Dict, Any, Optional
from src.model.move import Move, MoveFactory


def exp_for_level(level: int) -> int:
    """Medium-Fast experience formula: level^3."""
    return level ** 3


class Creature:
    """Base class for all creatures in the game."""

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
        status_effect: Optional[str] = None,
    ):
        self.species_id = species_id
        self.name = name
        self.types = [t.capitalize() for t in types]
        self.base_stats = base_stats.copy()
        self.level = level
        self.xp = exp_for_level(level) if xp is None else xp

        self.learnable_moves = learnable_moves or []
        self.evolution = evolution
        self.catch_rate = catch_rate
        self.base_xp = base_xp
        self.sprite_front = sprite_front
        self.sprite_back = sprite_back

        self.status_effect: Optional[str] = status_effect
        self.stat_stages: Dict[str, int] = {
            "attack": 0,
            "defense": 0,
            "sp_attack": 0,
            "sp_defense": 0,
            "speed": 0,
        }

        # Calculate actual stats from base stats and level
        self.stats: Dict[str, int] = {}
        self.recalculate_stats()

        # Current HP defaults to max_hp
        self.current_hp = self.max_hp if current_hp is None else min(current_hp, self.max_hp)

        # Active move pool (max 4 moves)
        self.moves: List[Move] = moves or []

    @property
    def primary_type(self) -> str:
        return self.types[0] if self.types else "Normal"

    @property
    def max_hp(self) -> int:
        return self.stats.get("hp", 10)

    @property
    def attack(self) -> int:
        return self._get_staged_stat("attack")

    @property
    def defense(self) -> int:
        return self._get_staged_stat("defense")

    @property
    def sp_attack(self) -> int:
        return self._get_staged_stat("sp_attack")

    @property
    def sp_defense(self) -> int:
        return self._get_staged_stat("sp_defense")

    @property
    def speed(self) -> int:
        spd = self._get_staged_stat("speed")
        if self.status_effect == "paralyze":
            spd = max(1, spd // 2)
        return spd

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    def recalculate_stats(self) -> None:
        """Calculate stats according to standard formula."""
        base_hp = self.base_stats.get("hp", 45)
        self.stats["hp"] = int((base_hp * 2 * self.level) / 100) + self.level + 10

        for stat_name in ("attack", "defense", "sp_attack", "sp_defense", "speed"):
            base_val = self.base_stats.get(stat_name, 50)
            self.stats[stat_name] = int((base_val * 2 * self.level) / 100) + 5

    def _get_staged_stat(self, stat_name: str) -> int:
        base = self.stats.get(stat_name, 10)
        stage = self.stat_stages.get(stat_name, 0)
        stage = max(-6, min(6, stage))
        if stage >= 0:
            multiplier = (2 + stage) / 2
        else:
            multiplier = 2 / (2 - stage)
        return max(1, int(base * multiplier))

    def reset_battle_stages(self) -> None:
        """Reset temporary combat stat buffs/debuffs."""
        for k in self.stat_stages:
            self.stat_stages[k] = 0

    def modify_stat_stage(self, stat_name: str, change: int) -> int:
        """Modify a stat stage by change (-6 to +6). Returns actual new stage."""
        if stat_name in self.stat_stages:
            old = self.stat_stages[stat_name]
            self.stat_stages[stat_name] = max(-6, min(6, old + change))
            return self.stat_stages[stat_name] - old
        return 0

    def take_damage(self, amount: int) -> int:
        """Apply damage to creature. Returns the actual amount of HP lost."""
        actual_damage = max(1, amount)
        actual_loss = min(self.current_hp, actual_damage)
        self.current_hp -= actual_loss
        if self.current_hp <= 0:
            self.current_hp = 0
            self.status_effect = None
        return actual_loss

    def heal(self, amount: int) -> int:
        """Restore HP. Cannot exceed max_hp. Returns amount healed."""
        if self.is_fainted:
            return 0
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - old_hp

    def revive(self, hp_fraction: float = 0.5) -> int:
        """Revive fainted creature with fraction of max HP."""
        if not self.is_fainted:
            return 0
        restored = max(1, int(self.max_hp * hp_fraction))
        self.current_hp = restored
        self.status_effect = None
        return restored

    def apply_status(self, status: str) -> bool:
        """Apply a status condition (burn, paralyze, poison, sleep)."""
        if self.is_fainted or self.status_effect is not None:
            return False
        self.status_effect = status.lower()
        return True

    def cure_status(self) -> Optional[str]:
        """Cure active status condition. Returns the name of the cured status."""
        cured = self.status_effect
        self.status_effect = None
        return cured

    def gain_xp(self, amount: int) -> Dict[str, Any]:
        """Award experience points and handle potential level ups."""
        self.xp += amount
        leveled_up = False
        initial_level = self.level

        while self.level < 100 and self.xp >= exp_for_level(self.level + 1):
            self.level += 1
            leveled_up = True
            old_max = self.max_hp
            self.recalculate_stats()
            # Increase current HP by the amount max HP grew
            self.current_hp += (self.max_hp - old_max)

        unlocked_move_ids: List[str] = []
        if leveled_up:
            for entry in self.learnable_moves:
                if initial_level < entry["level"] <= self.level:
                    unlocked_move_ids.append(entry["move_id"])

        return {
            "leveled_up": leveled_up,
            "old_level": initial_level,
            "new_level": self.level,
            "can_evolve": self.can_evolve(),
            "unlocked_moves": unlocked_move_ids,
        }

    def can_evolve(self) -> bool:
        """Check if creature meets evolution requirements."""
        if not self.evolution:
            return False
        required_level = self.evolution.get("level", 999)
        return self.level >= required_level

    def evolve(self, new_species_data: Dict[str, Any]) -> "Creature":
        """Transform this creature into its evolved form while keeping level, XP, and moves."""
        evolved = CreatureFactory.create(
            species_data=new_species_data,
            level=self.level,
            xp=self.xp,
            moves=self.moves,
        )
        evolved.current_hp = min(evolved.max_hp, self.current_hp + (evolved.max_hp - self.max_hp))
        evolved.status_effect = self.status_effect
        return evolved

    def learn_move(self, new_move: Move, slot: Optional[int] = None) -> bool:
        """Add a move to active move set (max 4). If slot given, replace that slot."""
        # Check if already knows move
        for m in self.moves:
            if m.id == new_move.id:
                return False

        if len(self.moves) < 4:
            self.moves.append(new_move)
            return True
        elif slot is not None and 0 <= slot < len(self.moves):
            self.moves[slot] = new_move
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize creature to a JSON-compatible dictionary."""
        return {
            "species_id": self.species_id,
            "name": self.name,
            "types": self.types,
            "level": self.level,
            "xp": self.xp,
            "current_hp": self.current_hp,
            "status_effect": self.status_effect,
            "moves": [m.to_dict() for m in self.moves],
            "base_stats": self.base_stats,
            "learnable_moves": self.learnable_moves,
            "evolution": self.evolution,
            "catch_rate": self.catch_rate,
            "base_xp": self.base_xp,
            "sprite_front": self.sprite_front,
            "sprite_back": self.sprite_back,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} Lv.{self.level} HP:{self.current_hp}/{self.max_hp}>"


class FireCreature(Creature):
    """Fire-type creature. Resistant to burns."""

    def apply_status(self, status: str) -> bool:
        if status.lower() == "burn":
            return False  # Fire types cannot be burned
        return super().apply_status(status)


class WaterCreature(Creature):
    """Water-type creature."""
    pass


class GrassCreature(Creature):
    """Grass-type creature. Immune to powder/spore moves."""

    def apply_status(self, status: str) -> bool:
        if status.lower() in ("poison", "sleep"):
            # Grass types have natural resilience
            pass
        return super().apply_status(status)


class ElectricCreature(Creature):
    """Electric-type creature. Immune to paralysis."""

    def apply_status(self, status: str) -> bool:
        if status.lower() == "paralyze":
            return False  # Electric types cannot be paralyzed
        return super().apply_status(status)


class NormalCreature(Creature):
    """Normal-type creature."""
    pass


class CreatureFactory:
    """Factory to create appropriate Creature subclass instances."""

    @staticmethod
    def create(
        species_data: Dict[str, Any],
        level: int = 5,
        xp: Optional[int] = None,
        moves: Optional[List[Move]] = None,
        current_hp: Optional[int] = None,
        status_effect: Optional[str] = None,
    ) -> Creature:
        types = species_data.get("types", ["Normal"])
        primary = types[0].capitalize() if types else "Normal"

        class_map = {
            "Fire": FireCreature,
            "Water": WaterCreature,
            "Grass": GrassCreature,
            "Electric": ElectricCreature,
            "Normal": NormalCreature,
        }

        creature_cls = class_map.get(primary, Creature)

        return creature_cls(
            species_id=species_data["id"],
            name=species_data["name"],
            types=types,
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
