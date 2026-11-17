"""Turn-based battle engine.

``Battle`` never draws or prints anything. Each action returns a list of
``BattleEvent`` objects that the UI plays back. It relies on polymorphism
instead of type checks:

* ``move.attack_stat()`` / ``move.defense_stat()``  Physical vs Special
* ``move.effect.apply()``                           each MoveEffect subclass
* ``status.before_move()`` / ``on_turn_end()``      each StatusCondition subclass
* ``item.use_in_battle()``                          each Item subclass (CatchBall throws)
"""
import random
from enum import Enum, auto
from typing import List, Optional

from src.model.creature import Creature
from src.model.events import BattleEvent, EventType
from src.model.move import Move, MoveFactory
from src.model.trainer import Trainer
from src.model.type_chart import TypeChart

# Re-exported so existing ``from src.model.battle import BattleEvent`` keeps working.
__all__ = ["Battle", "BattleState", "BattleEvent", "EventType"]

CRIT_CHANCE = 0.0625
CRIT_MULTIPLIER = 1.5
STAB_MULTIPLIER = 1.5


class BattleState(Enum):
    """Lifecycle states of a battle."""
    SELECTING_ACTION = auto()
    SELECTING_MOVE = auto()
    SELECTING_ITEM = auto()
    SELECTING_SWITCH = auto()
    EXECUTING_TURN = auto()
    WON = auto()
    LOST = auto()
    CAUGHT = auto()
    FLED = auto()


_ACTIVE_STATES = frozenset({
    BattleState.SELECTING_ACTION, BattleState.SELECTING_MOVE, BattleState.SELECTING_ITEM,
    BattleState.SELECTING_SWITCH, BattleState.EXECUTING_TURN,
})


class Battle:
    """A battle between the player's party and one wild creature."""

    def __init__(self, player: Trainer, wild_creature: Creature, type_chart: TypeChart):
        self._player = player
        self._wild = wild_creature
        self._type_chart = type_chart
        self._state = BattleState.SELECTING_ACTION
        self._turn_count = 0

        if self.player_creature:
            self.player_creature.reset_battle_stages()
        self._wild.reset_battle_stages()

    # ------------------------------------------------------------------
    # Read-only state
    # ------------------------------------------------------------------
    @property
    def player(self) -> Trainer:
        return self._player

    @property
    def wild_creature(self) -> Creature:
        return self._wild

    @property
    def state(self) -> BattleState:
        return self._state

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def player_creature(self) -> Optional[Creature]:
        return self._player.party.get_active()

    @property
    def is_active(self) -> bool:
        return self._state in _ACTIVE_STATES

    # ------------------------------------------------------------------
    # Player actions (public API)
    # ------------------------------------------------------------------
    def execute_move(self, player_move_index: int) -> List[BattleEvent]:
        """Play a full turn where the player uses the move in ``player_move_index``."""
        mine = self.player_creature
        if mine is None:
            self._state = BattleState.LOST
            return [BattleEvent(EventType.BATTLE_LOST, "You have no creatures that can fight!")]
        if not 0 <= player_move_index < len(mine.moves):
            return [self._invalid("Invalid move selection!")]
        my_move = mine.moves[player_move_index]
        if not my_move.can_use():
            return [self._invalid("No PP left for this move!")]

        self._turn_count += 1
        wild_move = self._choose_wild_move()
        order = [(mine, self._wild, my_move), (self._wild, mine, wild_move)]
        if self._wild_moves_first(mine):
            order.reverse()

        events: List[BattleEvent] = []
        for attacker, defender, move in order:
            if attacker.is_fainted:
                continue
            events += self._execute_move_step(attacker, defender, move)
            events += self._resolve_faints(mine)
            if not self.is_active or self._state is BattleState.SELECTING_SWITCH:
                return events

        events += self._end_of_turn(mine)
        return events

    def use_item(self, item_id: str) -> List[BattleEvent]:
        """Use an item from the bag. Each Item subclass decides what that means."""
        item = self._player.bag.get(item_id)
        if item is None or not item.has_stock():
            return [self._invalid(f"You don't have any {item_id}!")]

        events = item.use_in_battle(self)
        self._player.bag.remove_empty()
        took_turn = not any(e.event_type is EventType.INVALID_ACTION for e in events)
        if took_turn and self.is_active:
            self._turn_count += 1
            events += self._wild_free_attack()
        return events

    def attempt_catch(self, ball_id: str) -> List[BattleEvent]:
        """Throw the ball with id ``ball_id`` (kept for older callers; same as ``use_item``)."""
        return self.use_item(ball_id)

    def throw_ball(self, ball) -> List[BattleEvent]:
        """Called by ``CatchBall.use_in_battle``: throw ``ball`` at the wild creature."""
        if not ball.consume():
            return [self._invalid(f"No {ball.name} left!")]

        events = [BattleEvent(EventType.BALL_THROWN, f"{self._player.name} threw a {ball.name}!",
                              {"ball": ball.name})]
        if random.random() <= ball.calc_catch_chance(self._wild):
            self._state = BattleState.CAUGHT
            destination = self._player.receive_creature(self._wild)
            where = "" if destination == "party" else " It was sent to the PC."
            events.append(BattleEvent(
                EventType.CAUGHT, f"Gotcha! {self._wild.name} was caught!{where}",
                {"creature": self._wild.to_dict(), "destination": destination},
            ))
        else:
            events.append(BattleEvent(EventType.CATCH_FAILED, "Oh no! It broke free!",
                                      {"creature": self._wild.name}))
        return events

    def attempt_run(self) -> List[BattleEvent]:
        """Try to flee. Faster creatures escape more easily."""
        mine = self.player_creature
        if mine is None:
            self._state = BattleState.FLED
            return [BattleEvent(EventType.FLED, "Got away safely!")]

        chance = 0.50 + (mine.speed / max(1, self._wild.speed)) * 0.25
        if random.random() <= max(0.10, min(0.95, chance)):
            self._state = BattleState.FLED
            return [BattleEvent(EventType.FLED, "Got away safely!")]

        self._turn_count += 1
        return [BattleEvent(EventType.FLEE_FAILED, "Can't escape!")] + self._wild_free_attack()

    def switch_creature(self, party_index: int) -> List[BattleEvent]:
        """Send out the creature at ``party_index``."""
        party = self._player.party
        if not 0 <= party_index < party.size:
            return [self._invalid("Invalid party slot!")]
        chosen = party.creatures[party_index]
        if chosen.is_fainted:
            return [self._invalid(f"{chosen.name} has no energy left to battle!")]

        party.swap(0, party_index)
        chosen.reset_battle_stages()
        self._state = BattleState.SELECTING_ACTION
        return [BattleEvent(EventType.CREATURE_SENT, f"Go! {chosen.name}!", {"creature": chosen.name})]

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------
    def calculate_damage(self, attacker: Creature, defender: Creature, move: Move) -> dict:
        """Roll accuracy, crit and variance, and compute damage for ``move``."""
        if not move.is_damaging() or move.power <= 0:
            return {"damage": 0, "multiplier": 1.0, "is_crit": False, "hit": True}
        if random.randint(1, 100) > move.accuracy:
            return {"damage": 0, "multiplier": 1.0, "is_crit": False, "hit": False}

        atk = move.attack_stat(attacker)
        dfn = move.defense_stat(defender)
        is_crit = random.random() < CRIT_CHANCE
        base = ((2 * attacker.level / 5 + 2) * move.power * (atk / max(1, dfn))) / 50 + 2
        stab = STAB_MULTIPLIER if move.type in attacker.types else 1.0
        type_mult = self._type_chart.get_effectiveness(move.type, list(defender.types))
        crit = CRIT_MULTIPLIER if is_crit else 1.0
        damage = int(base * stab * type_mult * crit * random.uniform(0.85, 1.0))
        damage = max(1, damage) if type_mult > 0 else 0
        return {"damage": damage, "multiplier": type_mult, "is_crit": is_crit, "hit": True}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _invalid(message: str) -> BattleEvent:
        return BattleEvent(EventType.INVALID_ACTION, message)

    def _wild_moves_first(self, mine: Creature) -> bool:
        if mine.speed != self._wild.speed:
            return self._wild.speed > mine.speed
        return random.random() < 0.5

    def _choose_wild_move(self) -> Move:
        usable = [m for m in self._wild.moves if m.can_use()]
        return random.choice(usable) if usable else MoveFactory.struggle()

    def _wild_free_attack(self) -> List[BattleEvent]:
        """The wild creature attacks after the player spends a turn on something else."""
        mine = self.player_creature
        if mine is None or self._wild.is_fainted:
            return []
        events = self._execute_move_step(self._wild, mine, self._choose_wild_move())
        events += self._resolve_faints(mine)
        if self.is_active and self._state is not BattleState.SELECTING_SWITCH:
            events += self._end_of_turn(mine)
        return events

    def _execute_move_step(self, user: Creature, target: Creature, move: Move) -> List[BattleEvent]:
        """One creature uses one move."""
        events: List[BattleEvent] = []

        if user.status:
            can_act, message = user.status.before_move(user)
            if message:
                kind = EventType.STATUS_HINDRANCE if not can_act else EventType.STATUS_CURED
                events.append(BattleEvent(kind, message, {"creature": user.name}))
            if not can_act:
                return events

        move.use()
        events.append(BattleEvent(EventType.MOVE_USED, f"{user.name} used {move.name}!",
                                  {"user": user.name, "move": move.name, "type": move.type}))

        calc = self.calculate_damage(user, target, move)
        if not calc["hit"]:
            events.append(BattleEvent(EventType.MISSED, f"{user.name}'s attack missed!",
                                      {"user": user.name, "target": target.name}))
            return events
        if calc["multiplier"] == 0.0:
            events.append(BattleEvent(EventType.NO_EFFECT, f"It had no effect on {target.name}!",
                                      {"target": target.name}))
            return events

        if calc["damage"] > 0:
            lost = target.take_damage(calc["damage"])
            events.append(BattleEvent(
                EventType.DAMAGE_DEALT, f"{target.name} took {lost} damage!",
                {"target": target.name, "damage": lost,
                 "target_current_hp": target.current_hp, "target_max_hp": target.max_hp},
            ))
            if calc["is_crit"]:
                events.append(BattleEvent(EventType.CRITICAL, "A critical hit!"))
            eff_msg = self._type_chart.get_effectiveness_message(calc["multiplier"])
            if eff_msg:
                events.append(BattleEvent(EventType.EFFECTIVENESS, eff_msg,
                                          {"multiplier": calc["multiplier"]}))

        if move.effect and not target.is_fainted:
            effect_events = move.effect.apply(user, target) if move.effect.triggers() else []
            if not effect_events and not move.is_damaging():
                effect_events = [BattleEvent(EventType.FAILED, "But it failed!")]
            events += effect_events

        if target.is_fainted:
            events.append(BattleEvent(EventType.FAINTED, f"{target.name} fainted!",
                                      {"fainted": target.name}))
        return events

    def _end_of_turn(self, mine: Creature) -> List[BattleEvent]:
        """Status damage for both sides, then check for faints."""
        events: List[BattleEvent] = []
        for creature in (mine, self._wild):
            if creature.is_fainted or not creature.status:
                continue
            status_key = creature.status.key
            damage, message = creature.status.on_turn_end(creature)
            if damage <= 0:
                continue
            creature.take_damage(damage)
            events.append(BattleEvent(
                EventType.STATUS_DAMAGE, message,
                {"target": creature.name, "creature": creature.name, "damage": damage,
                 "status": status_key, "target_current_hp": creature.current_hp,
                 "target_max_hp": creature.max_hp},
            ))
            if creature.is_fainted:
                events.append(BattleEvent(EventType.FAINTED, f"{creature.name} fainted!",
                                          {"fainted": creature.name}))
        return events + self._resolve_faints(mine)

    def _resolve_faints(self, mine: Creature) -> List[BattleEvent]:
        """After damage: decide whether the battle is won, lost, or needs a switch."""
        if self._wild.is_fainted:
            self._state = BattleState.WON
            return self._award_victory_xp(mine) + [
                BattleEvent(EventType.BATTLE_WON, f"Defeated wild {self._wild.name}!")]
        if mine.is_fainted:
            if self._player.party.all_fainted():
                self._state = BattleState.LOST
                return [BattleEvent(EventType.BATTLE_LOST,
                                    f"{self._player.name} is out of usable creatures! You blacked out!")]
            self._state = BattleState.SELECTING_SWITCH
            return [BattleEvent(EventType.CHOOSE_NEXT, "Send out another creature?")]
        return []

    def _award_victory_xp(self, winner: Creature) -> List[BattleEvent]:
        if winner.is_fainted:
            return []
        xp = max(1, int(self._wild.base_xp * self._wild.level / 7))
        events = [BattleEvent(EventType.XP_GAINED, f"{winner.name} gained {xp} EXP. Points!",
                              {"creature": winner.name, "xp": xp})]
        result = winner.gain_xp(xp)
        if result["leveled_up"]:
            events.append(BattleEvent(EventType.LEVEL_UP,
                                      f"{winner.name} grew to level {result['new_level']}!", result))
            for move_id in result["unlocked_moves"]:
                events.append(BattleEvent(EventType.UNLOCKED_MOVE,
                                          f"{winner.name} can learn a new move ({move_id})!",
                                          {"move_id": move_id}))
        return events
