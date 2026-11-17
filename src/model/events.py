"""Battle events: the immutable messages the battle model sends to whatever displays it."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class EventType(str, Enum):
    """Every kind of thing that can happen in a battle.

    Inherits from ``str`` so ``EventType.FAINTED == "fainted"`` is True, which
    keeps older string comparisons working.
    """
    MOVE_USED = "move_used"
    MISSED = "missed"
    NO_EFFECT = "no_effect"
    FAILED = "failed"
    DAMAGE_DEALT = "damage_dealt"
    CRITICAL = "critical"
    EFFECTIVENESS = "effectiveness"
    FAINTED = "fainted"
    STATUS_APPLIED = "status_applied"
    STATUS_HINDRANCE = "status_hindrance"
    STATUS_DAMAGE = "status_damage"
    STATUS_CURED = "status_cured"
    HEAL = "heal"
    STAT_CHANGE = "stat_change"
    XP_GAINED = "xp_gained"
    LEVEL_UP = "level_up"
    UNLOCKED_MOVE = "unlocked_move"
    MOVE_LEARNED = "move_learned"
    LEARN_MOVE_PROMPT = "learn_move_prompt"
    MOVE_NOT_LEARNED = "move_not_learned"
    ITEM_USED = "item_used"
    BALL_THROWN = "ball_thrown"
    CAUGHT = "caught"
    CATCH_FAILED = "catch_failed"
    FLED = "fled"
    FLEE_FAILED = "flee_failed"
    CREATURE_SENT = "creature_sent"
    OPPONENT_SENT = "opponent_sent"
    PRIZE_MONEY = "prize_money"
    BADGE_EARNED = "badge_earned"
    CHOOSE_NEXT = "choose_next"
    BATTLE_WON = "battle_won"
    BATTLE_LOST = "battle_lost"
    INVALID_ACTION = "invalid_action"


@dataclass(frozen=True)
class BattleEvent:
    """One thing that happened in battle, for the UI to animate and show."""
    event_type: EventType
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
