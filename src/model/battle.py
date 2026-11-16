"""Turn-based battle engine and battle event system."""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import random

from src.model.creature import Creature
from src.model.move import Move
from src.model.item import CatchBall
from src.model.trainer import Trainer
from src.model.type_chart import TypeChart


class BattleState(Enum):
    """Lifecycle states of a battle encounter."""
    SELECTING_ACTION = auto()
    SELECTING_MOVE = auto()
    SELECTING_ITEM = auto()
    SELECTING_SWITCH = auto()
    EXECUTING_TURN = auto()
    WON = auto()
    LOST = auto()
    CAUGHT = auto()
    FLED = auto()


@dataclass
class BattleEvent:
    """Represents a discrete event during battle for UI animation and logging."""
    event_type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


class Battle:
    """Manages turn-based combat between a player's active creature and a wild creature."""

    def __init__(
        self,
        player: Trainer,
        wild_creature: Creature,
        type_chart: TypeChart,
    ):
        self.player = player
        self.wild_creature = wild_creature
        self.type_chart = type_chart
        self.state = BattleState.SELECTING_ACTION
        self.turn_count = 0

        # Reset stat stages at battle start
        if self.player_creature:
            self.player_creature.reset_battle_stages()
        self.wild_creature.reset_battle_stages()

    @property
    def player_creature(self) -> Optional[Creature]:
        return self.player.party.get_active()

    @property
    def is_active(self) -> bool:
        return self.state in (
            BattleState.SELECTING_ACTION,
            BattleState.SELECTING_MOVE,
            BattleState.SELECTING_ITEM,
            BattleState.SELECTING_SWITCH,
            BattleState.EXECUTING_TURN,
        )

    def calculate_damage(self, attacker: Creature, defender: Creature, move: Move) -> Dict[str, Any]:
        """Calculates combat damage, critical hit, and type effectiveness."""
        if not move.is_damaging() or move.power <= 0:
            return {"damage": 0, "multiplier": 1.0, "is_crit": False, "hit": True}

        # Accuracy check
        roll = random.randint(1, 100)
        if roll > move.accuracy:
            return {"damage": 0, "multiplier": 1.0, "is_crit": False, "hit": False}

        # Attack and defense stats based on category
        if move.category == "special":
            atk = attacker.sp_attack
            dfn = defender.sp_defense
        else:
            atk = attacker.attack
            dfn = defender.defense

        # Critical hit (~6.25% chance)
        is_crit = random.random() < 0.0625
        crit_multiplier = 1.5 if is_crit else 1.0

        # Base damage formula (classic formula)
        base = ((2 * attacker.level / 5 + 2) * move.power * (atk / max(1, dfn))) / 50 + 2

        # STAB (Same Type Attack Bonus: 1.5x)
        stab = 1.5 if move.type in attacker.types else 1.0

        # Type effectiveness
        type_mult = self.type_chart.get_effectiveness(move.type, defender.types)

        # Random variance 85% to 100%
        variance = random.uniform(0.85, 1.0)

        total_damage = int(base * stab * type_mult * crit_multiplier * variance)
        if type_mult > 0.0:
            total_damage = max(1, total_damage)
        else:
            total_damage = 0

        return {
            "damage": total_damage,
            "multiplier": type_mult,
            "is_crit": is_crit,
            "hit": True,
        }

    def _execute_move_step(self, user: Creature, target: Creature, move: Move) -> List[BattleEvent]:
        """Execute a single creature's move and return the resulting events."""
        events: List[BattleEvent] = []

        # Check status hindrance (paralysis full paralyze 25%, sleep)
        if user.status_effect == "paralyze" and random.random() < 0.25:
            events.append(BattleEvent(
                event_type="status_hindrance",
                message=f"{user.name} is fully paralyzed! It can't move!",
                data={"creature": user.name, "status": "paralyze"},
            ))
            return events

        if user.status_effect == "sleep":
            events.append(BattleEvent(
                event_type="status_hindrance",
                message=f"{user.name} is fast asleep!",
                data={"creature": user.name, "status": "sleep"},
            ))
            return events

        # Deduct PP
        user_move_used = move.use()
        events.append(BattleEvent(
            event_type="move_used",
            message=f"{user.name} used {move.name}!",
            data={"user": user.name, "move": move.name, "type": move.type},
        ))

        # Handle damage
        calc = self.calculate_damage(user, target, move)
        if not calc["hit"]:
            events.append(BattleEvent(
                event_type="missed",
                message=f"{user.name}'s attack missed!",
                data={"user": user.name, "target": target.name},
            ))
            return events

        if calc["multiplier"] == 0.0:
            events.append(BattleEvent(
                event_type="no_effect",
                message=f"It had no effect on {target.name}!",
                data={"target": target.name},
            ))
            return events

        if calc["damage"] > 0:
            actual_dmg = target.take_damage(calc["damage"])
            events.append(BattleEvent(
                event_type="damage_dealt",
                message=f"{target.name} took {actual_dmg} damage!",
                data={
                    "target": target.name,
                    "damage": actual_dmg,
                    "target_current_hp": target.current_hp,
                    "target_max_hp": target.max_hp,
                },
            ))

            if calc["is_crit"]:
                events.append(BattleEvent(
                    event_type="critical",
                    message="A critical hit!",
                ))

            eff_msg = self.type_chart.get_effectiveness_message(calc["multiplier"])
            if eff_msg:
                events.append(BattleEvent(
                    event_type="effectiveness",
                    message=eff_msg,
                    data={"multiplier": calc["multiplier"]},
                ))

        # Handle secondary effects or status moves
        if move.effect:
            eff_events = self._apply_move_effect(user, target, move)
            events.extend(eff_events)

        # Check if target fainted
        if target.is_fainted:
            events.append(BattleEvent(
                event_type="fainted",
                message=f"{target.name} fainted!",
                data={"fainted": target.name},
            ))

        return events

    def _apply_move_effect(self, user: Creature, target: Creature, move: Move) -> List[BattleEvent]:
        events: List[BattleEvent] = []
        chance = move.effect_chance / 100.0
        if random.random() > chance:
            return events

        effect = move.effect.lower()
        if effect in ("burn", "paralyze", "poison", "sleep"):
            if target.apply_status(effect):
                msg_map = {
                    "burn": f"{target.name} was burned!",
                    "paralyze": f"{target.name} is paralyzed! It may be unable to move!",
                    "poison": f"{target.name} was poisoned!",
                    "sleep": f"{target.name} fell asleep!",
                }
                events.append(BattleEvent(
                    event_type="status_applied",
                    message=msg_map.get(effect, f"{target.name} gained {effect}!"),
                    data={"target": target.name, "status": effect},
                ))
        elif effect == "heal":
            healed = user.heal(user.max_hp // 2)
            events.append(BattleEvent(
                event_type="heal",
                message=f"{user.name} restored {healed} HP!",
                data={"user": user.name, "healed": healed},
            ))
        elif effect == "stat_lower_attack":
            chg = target.modify_stat_stage("attack", -1)
            if chg != 0:
                events.append(BattleEvent(
                    event_type="stat_change",
                    message=f"{target.name}'s Attack fell!",
                    data={"target": target.name, "stat": "attack", "change": -1},
                ))
        elif effect == "stat_lower_defense":
            chg = target.modify_stat_stage("defense", -1)
            if chg != 0:
                events.append(BattleEvent(
                    event_type="stat_change",
                    message=f"{target.name}'s Defense fell!",
                    data={"target": target.name, "stat": "defense", "change": -1},
                ))

        return events

    def _apply_end_of_turn_effects(self, creature: Creature) -> List[BattleEvent]:
        """Apply passive status damage at turn end (burn, poison)."""
        events: List[BattleEvent] = []
        if creature.is_fainted or not creature.status_effect:
            return events

        if creature.status_effect in ("poison", "burn"):
            dmg = max(1, creature.max_hp // 16)
            creature.take_damage(dmg)
            tag = "hurt by poison" if creature.status_effect == "poison" else "hurt by its burn"
            events.append(BattleEvent(
                event_type="status_damage",
                message=f"{creature.name} was {tag}!",
                data={"creature": creature.name, "damage": dmg, "status": creature.status_effect},
            ))
            if creature.is_fainted:
                events.append(BattleEvent(
                    event_type="fainted",
                    message=f"{creature.name} fainted!",
                    data={"fainted": creature.name},
                ))

        return events

    def _award_victory_xp(self) -> List[BattleEvent]:
        """Calculate and award XP to active player creature upon victory."""
        events: List[BattleEvent] = []
        lead = self.player_creature
        if not lead:
            return events

        # Classic XP reward formula
        xp_gain = int((self.wild_creature.base_xp * self.wild_creature.level) / 7)
        xp_gain = max(1, xp_gain)

        events.append(BattleEvent(
            event_type="xp_gained",
            message=f"{lead.name} gained {xp_gain} EXP. Points!",
            data={"creature": lead.name, "xp": xp_gain},
        ))

        level_info = lead.gain_xp(xp_gain)
        if level_info["leveled_up"]:
            events.append(BattleEvent(
                event_type="level_up",
                message=f"{lead.name} grew to level {level_info['new_level']}!",
                data=level_info,
            ))
            for new_move_id in level_info.get("unlocked_moves", []):
                events.append(BattleEvent(
                    event_type="unlocked_move",
                    message=f"{lead.name} can learn a new move ({new_move_id})!",
                    data={"move_id": new_move_id},
                ))

        return events

    def execute_move(self, player_move_index: int) -> List[BattleEvent]:
        """Execute a full turn where the player chose to use a move."""
        events: List[BattleEvent] = []
        player_creature = self.player_creature

        if not player_creature or player_creature.is_fainted:
            self.state = BattleState.LOST
            events.append(BattleEvent(
                event_type="battle_lost",
                message="You have no usable creatures!",
            ))
            return events

        if not (0 <= player_move_index < len(player_creature.moves)):
            events.append(BattleEvent(
                event_type="invalid_action",
                message="Invalid move selection!",
            ))
            return events

        player_move = player_creature.moves[player_move_index]
        if not player_move.can_use():
            events.append(BattleEvent(
                event_type="invalid_action",
                message="No PP left for this move!",
            ))
            return events

        # Enemy AI picks a move with remaining PP
        wild_moves = [m for m in self.wild_creature.moves if m.can_use()]
        if not wild_moves:
            wild_move = MoveFactory.from_json({
                "id": "struggle",
                "name": "Struggle",
                "type": "Normal",
                "category": "physical",
                "power": 50,
                "accuracy": 100,
                "pp": 10,
            })
        else:
            wild_move = random.choice(wild_moves)

        self.turn_count += 1

        # Determine turn order based on speed
        player_speed = player_creature.speed
        wild_speed = self.wild_creature.speed
        player_first = (player_speed > wild_speed) if player_speed != wild_speed else random.choice([True, False])

        first_turn = (player_creature, self.wild_creature, player_move, True) if player_first else (self.wild_creature, player_creature, wild_move, False)
        second_turn = (self.wild_creature, player_creature, wild_move, False) if player_first else (player_creature, self.wild_creature, player_move, True)

        # 1. First creature attacks
        attacker, defender, move, is_player = first_turn
        events.extend(self._execute_move_step(attacker, defender, move))

        # Check if combat concluded after first strike
        if defender.is_fainted:
            if is_player:  # Wild creature was defeated!
                self.state = BattleState.WON
                events.extend(self._award_victory_xp())
                events.append(BattleEvent(
                    event_type="battle_won",
                    message=f"Defeated wild {self.wild_creature.name}!",
                ))
            else:  # Player creature was defeated!
                if self.player.party.all_fainted():
                    self.state = BattleState.LOST
                    events.append(BattleEvent(
                        event_type="battle_lost",
                        message=f"{self.player.name} is out of usable creatures! You blacked out!",
                    ))
                else:
                    self.state = BattleState.SELECTING_SWITCH
                    events.append(BattleEvent(
                        event_type="choose_next",
                        message=f"Send out another creature?",
                    ))
            return events

        # 2. Second creature attacks (if alive)
        attacker, defender, move, is_player = second_turn
        events.extend(self._execute_move_step(attacker, defender, move))

        if defender.is_fainted:
            if is_player:  # Wild creature was defeated!
                self.state = BattleState.WON
                events.extend(self._award_victory_xp())
                events.append(BattleEvent(
                    event_type="battle_won",
                    message=f"Defeated wild {self.wild_creature.name}!",
                ))
            else:  # Player creature fainted!
                if self.player.party.all_fainted():
                    self.state = BattleState.LOST
                    events.append(BattleEvent(
                        event_type="battle_lost",
                        message=f"{self.player.name} is out of usable creatures! You blacked out!",
                    ))
                else:
                    self.state = BattleState.SELECTING_SWITCH
                    events.append(BattleEvent(
                        event_type="choose_next",
                        message=f"Send out another creature?",
                    ))
            return events

        # 3. End-of-turn status damage
        events.extend(self._apply_end_of_turn_effects(player_creature))
        events.extend(self._apply_end_of_turn_effects(self.wild_creature))

        if self.wild_creature.is_fainted:
            self.state = BattleState.WON
            events.extend(self._award_victory_xp())
        elif player_creature.is_fainted:
            if self.player.party.all_fainted():
                self.state = BattleState.LOST
            else:
                self.state = BattleState.SELECTING_SWITCH

        return events

    def attempt_catch(self, ball_id: str) -> List[BattleEvent]:
        """Attempt to capture the wild creature using a CatchBall item."""
        events: List[BattleEvent] = []
        item = self.player.get_item(ball_id)

        if not item or not isinstance(item, CatchBall) or not item.has_stock():
            events.append(BattleEvent(
                event_type="invalid_action",
                message=f"No {ball_id} available to throw!",
            ))
            return events

        # Consume the ball
        item.consume()
        if item.quantity <= 0:
            del self.player.inventory[ball_id]

        events.append(BattleEvent(
            event_type="ball_thrown",
            message=f"{self.player.name} threw a {item.name}!",
            data={"ball": item.name},
        ))

        # Calculate catch probability
        chance = item.calc_catch_chance(self.wild_creature)
        roll = random.random()

        if roll <= chance:
            self.state = BattleState.CAUGHT
            # Add to party if space permits
            added_to_party = self.player.party.add(self.wild_creature)
            dest = "party" if added_to_party else "storage"
            events.append(BattleEvent(
                event_type="caught",
                message=f"Gotcha! {self.wild_creature.name} was caught!",
                data={
                    "creature": self.wild_creature.to_dict(),
                    "destination": dest,
                },
            ))
        else:
            events.append(BattleEvent(
                event_type="catch_failed",
                message=f"Oh no! The creature broke free!",
                data={"creature": self.wild_creature.name},
            ))

            # Wild creature retaliates with an attack!
            wild_moves = [m for m in self.wild_creature.moves if m.can_use()]
            if wild_moves and self.player_creature:
                wild_move = random.choice(wild_moves)
                events.extend(self._execute_move_step(self.wild_creature, self.player_creature, wild_move))
                if self.player_creature.is_fainted:
                    if self.player.party.all_fainted():
                        self.state = BattleState.LOST
                    else:
                        self.state = BattleState.SELECTING_SWITCH

        return events

    def attempt_run(self) -> List[BattleEvent]:
        """Attempt to flee from the battle based on relative speed."""
        events: List[BattleEvent] = []
        player_creature = self.player_creature

        if not player_creature:
            self.state = BattleState.FLED
            events.append(BattleEvent(event_type="fled", message="Got away safely!"))
            return events

        p_speed = player_creature.speed
        w_speed = self.wild_creature.speed

        # Formula: 50% base + speed ratio * 25%, capped at 95%
        flee_chance = 0.50 + ((p_speed / max(1, w_speed)) * 0.25)
        flee_chance = max(0.10, min(0.95, flee_chance))

        if random.random() <= flee_chance:
            self.state = BattleState.FLED
            events.append(BattleEvent(
                event_type="fled",
                message="Got away safely!",
            ))
        else:
            events.append(BattleEvent(
                event_type="flee_failed",
                message="Can't escape!",
            ))
            # Enemy attacks on failed escape
            wild_moves = [m for m in self.wild_creature.moves if m.can_use()]
            if wild_moves:
                wild_move = random.choice(wild_moves)
                events.extend(self._execute_move_step(self.wild_creature, player_creature, wild_move))
                if player_creature.is_fainted:
                    if self.player.party.all_fainted():
                        self.state = BattleState.LOST
                    else:
                        self.state = BattleState.SELECTING_SWITCH

        return events

    def switch_creature(self, party_index: int) -> List[BattleEvent]:
        """Swap active creature with one from party."""
        events: List[BattleEvent] = []
        if not (0 <= party_index < len(self.player.party.creatures)):
            events.append(BattleEvent(event_type="invalid_action", message="Invalid party slot!"))
            return events

        chosen = self.player.party.creatures[party_index]
        if chosen.is_fainted:
            events.append(BattleEvent(event_type="invalid_action", message=f"{chosen.name} has no energy left to battle!"))
            return events

        # Swap to slot 0 so it becomes active
        self.player.party.swap(0, party_index)
        chosen.reset_battle_stages()

        events.append(BattleEvent(
            event_type="creature_sent",
            message=f"Go! {chosen.name}!",
            data={"creature": chosen.name},
        ))

        self.state = BattleState.SELECTING_ACTION
        return events
