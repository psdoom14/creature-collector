"""Developer / demo helpers used by the debug menu.

They change the game state only through the normal public methods (``gain_xp``,
``learn_move``, ``receive_creature``, ``Bag.add`` / ``remove``, ``earn`` / ``spend``),
so even the debug menu can't break a game rule such as "at most 6 in the party".
"""
from typing import Any, Callable, Dict, List

from src.model.creature import MAX_LEVEL, Creature, exp_for_level
from src.model.errors import RuleViolation
from src.model.move import Move
from src.model.trainer import Trainer

MoveSource = Callable[[str], Move]


def level_up(creature: Creature, levels: int, move_source: MoveSource) -> Dict[str, Any]:
    """Raise ``creature`` by ``levels`` (capped at 100), learning new moves while it has a free slot."""
    target = min(MAX_LEVEL, creature.level + max(0, levels))
    result = creature.gain_xp(max(0, exp_for_level(target) - creature.xp))
    learned: List[str] = []
    for move_id in result["unlocked_moves"]:
        if not creature.knows_move(move_id) and creature.learn_move(move_source(move_id)):
            learned.append(move_id)
    result["learned"] = learned
    return result


def add_creature(trainer: Trainer, creature: Creature) -> str:
    """Give the trainer a creature. Returns "party" or "pc" (when the party is full)."""
    return trainer.receive_creature(creature)


def remove_creature(trainer: Trainer, index: int) -> Creature:
    """Release the party creature at ``index``. The last creature can't be removed."""
    party = trainer.party
    if party.size <= 1:
        raise RuleViolation("You can't remove your last creature")
    removed = party.remove(index)
    if removed is None:
        raise RuleViolation(f"No creature in party slot {index + 1}")
    return removed


def change_money(trainer: Trainer, amount: int) -> int:
    """Add (or with a negative amount, take away) money, never going below zero. Returns the new total."""
    if amount >= 0:
        trainer.earn(amount)
    else:
        trainer.spend(min(trainer.money, -amount))
    return trainer.money
