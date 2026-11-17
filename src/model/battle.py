"""Turn-based battle engine.

    Battle (abstract)      all the turn rules
    ├── WildBattle         you may run and throw balls
    └── TrainerBattle      no running or catching; the trainer sends out their next
        │                  creature, pays prize money and remembers being beaten
        └── GymBattle      ...and awards a badge

Subclasses only override hooks: ``can_flee``, ``can_catch``, ``intro_message``,
``_on_opponent_fainted()``, ``_xp_multiplier`` and ``_victory_extras()``.

``Battle`` never draws or prints anything. Each action returns a list of
``BattleEvent`` objects that the UI plays back. It relies on polymorphism
instead of type checks:

* ``move.attack_stat()`` / ``move.defense_stat()``  Physical vs Special
* ``move.effect.apply()``                           each MoveEffect subclass
* ``status.before_move()`` / ``on_turn_end()``      each StatusCondition subclass
* ``item.use_in_battle()``                          each Item subclass (CatchBall throws)
* ``ai.choose_move()``                              each BattleAI subclass
"""
import random
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from src.model.battle_ai import BattleAI, RandomAI
from src.model.creature import Creature
from src.model.events import BattleEvent, EventType
from src.model.move import Move
from src.model.trainer import Trainer
from src.model.type_chart import TypeChart

__all__ = ["Battle", "WildBattle", "TrainerBattle", "GymBattle", "BattleState", "BattleEvent", "EventType"]

CRIT_CHANCE = 0.0625
CRIT_MULTIPLIER = 1.5
STAB_MULTIPLIER = 1.5

MoveSource = Callable[[str], Move]


class BattleState(Enum):
    """Lifecycle states of a battle."""
    SELECTING_ACTION = auto()
    SELECTING_SWITCH = auto()   # the player's creature fainted and a replacement must be chosen
    WON = auto()
    LOST = auto()
    CAUGHT = auto()
    FLED = auto()


_ACTIVE_STATES = frozenset({BattleState.SELECTING_ACTION, BattleState.SELECTING_SWITCH})


class Battle(ABC):
    """Abstract battle between the player's party and one opposing creature."""

    def __init__(
        self,
        player: Trainer,
        opponent: Creature,
        type_chart: TypeChart,
        ai: Optional[BattleAI] = None,
        move_source: Optional[MoveSource] = None,
    ):
        self._player = player
        self._opponent = opponent
        self._type_chart = type_chart
        self._ai = ai or RandomAI()
        self._move_source = move_source
        self._state = BattleState.SELECTING_ACTION
        self._turn_count = 0
        self._active: Optional[Creature] = player.party.get_active()
        self._pending_moves: List[Tuple[Creature, Move]] = []

        if self._active:
            self._active.reset_battle_stages()
        self._opponent.reset_battle_stages()

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def can_flee(self) -> bool:
        """Whether the player may run from this battle."""

    @property
    @abstractmethod
    def can_catch(self) -> bool:
        """Whether balls can be thrown at the opponent."""

    @property
    @abstractmethod
    def intro_message(self) -> str:
        """Text shown when the battle starts."""

    @abstractmethod
    def _on_opponent_fainted(self) -> List[BattleEvent]:
        """The current opponent fainted: end the battle or bring out the next one."""

    @property
    def _xp_multiplier(self) -> float:
        """Bonus XP for this kind of battle (trainers give more than wild creatures)."""
        return 1.0

    @property
    def after_battle_lines(self) -> Tuple[str, ...]:
        """What someone says in the overworld once the battle is over (nothing, for wild battles)."""
        return ()

    # ------------------------------------------------------------------
    # Read-only state
    # ------------------------------------------------------------------
    @property
    def player(self) -> Trainer:
        return self._player

    @property
    def opponent(self) -> Creature:
        return self._opponent

    @property
    def state(self) -> BattleState:
        return self._state

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def player_creature(self) -> Optional[Creature]:
        """The player's creature currently out (may be fainted while a switch is pending)."""
        return self._active

    @property
    def is_active(self) -> bool:
        return self._state in _ACTIVE_STATES

    @property
    def pending_move(self) -> Optional[Move]:
        """A move waiting for the player to decide which old move to forget."""
        return self._pending_moves[0][1] if self._pending_moves else None

    @property
    def pending_learner(self) -> Optional[Creature]:
        return self._pending_moves[0][0] if self._pending_moves else None

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------
    def execute_move(self, player_move_index: int) -> List[BattleEvent]:
        """Play a full turn where the player uses the move in ``player_move_index``."""
        blocked = self._check_can_act()
        if blocked:
            return blocked
        mine = self._active
        if not 0 <= player_move_index < len(mine.moves):
            return [self._invalid("Invalid move selection!")]
        my_move = mine.moves[player_move_index]
        if not my_move.can_use():
            return [self._invalid("No PP left for this move!")]

        self._turn_count += 1
        their_move = self._ai.choose_move(self._opponent, mine)
        order = [(mine, self._opponent, my_move), (self._opponent, mine, their_move)]
        if self._opponent_moves_first(mine):
            order.reverse()

        events: List[BattleEvent] = []
        for attacker, defender, move in order:
            if attacker.is_fainted:
                continue
            events += self._execute_move_step(attacker, defender, move)
            events += self._resolve_faints()
            if self._turn_over():
                return events
        return events + self._end_of_turn()

    def use_item(self, item_id: str) -> List[BattleEvent]:
        """Use an item from the bag. Each Item subclass decides what that means."""
        blocked = self._check_can_act()
        if blocked:
            return blocked
        item = self._player.bag.get(item_id)
        if item is None or not item.has_stock():
            return [self._invalid(f"You don't have any {item_id}!")]

        events = item.use_in_battle(self)
        self._player.bag.remove_empty()
        took_turn = not any(e.event_type is EventType.INVALID_ACTION for e in events)
        if took_turn and self.is_active:
            self._turn_count += 1
            events += self._opponent_free_attack()
        return events

    def attempt_catch(self, ball_id: str) -> List[BattleEvent]:
        """Throw the ball with id ``ball_id`` (same as ``use_item``)."""
        return self.use_item(ball_id)

    def throw_ball(self, ball) -> List[BattleEvent]:
        """Called by ``CatchBall.use_in_battle``: throw ``ball`` at the opponent."""
        if not self.can_catch:
            return [self._invalid("You can't catch another trainer's creature!")]
        if not ball.consume():
            return [self._invalid(f"No {ball.name} left!")]

        foe = self._opponent
        events = [BattleEvent(EventType.BALL_THROWN, f"{self._player.name} threw a {ball.name}!",
                              {"ball": ball.name})]
        if random.random() <= ball.calc_catch_chance(foe):
            self._state = BattleState.CAUGHT
            destination = self._player.receive_creature(foe)
            where = "" if destination == "party" else " It was sent to the PC."
            events.append(BattleEvent(
                EventType.CAUGHT, f"Gotcha! {foe.name} was caught!{where}",
                {"creature": foe.to_dict(), "destination": destination, "uid": foe.uid},
            ))
        else:
            events.append(BattleEvent(EventType.CATCH_FAILED, "Oh no! It broke free!",
                                      {"creature": foe.name}))
        return events

    def attempt_run(self) -> List[BattleEvent]:
        """Try to flee. Faster creatures escape more easily."""
        blocked = self._check_can_act()
        if blocked:
            return blocked
        if not self.can_flee:
            return [self._invalid("No! There's no running from this battle!")]

        mine = self._active
        chance = 0.50 + (mine.speed / max(1, self._opponent.speed)) * 0.25
        if random.random() <= max(0.10, min(0.95, chance)):
            self._state = BattleState.FLED
            return [BattleEvent(EventType.FLED, "Got away safely!")]

        self._turn_count += 1
        return [BattleEvent(EventType.FLEE_FAILED, "Can't escape!")] + self._opponent_free_attack()

    def switch_creature(self, party_index: int) -> List[BattleEvent]:
        """Send out the party creature at ``party_index``.

        After a faint this is free; otherwise it uses the player's turn.
        """
        if not self.is_active:
            return [self._invalid("The battle is over!")]
        party = self._player.party
        if not 0 <= party_index < party.size:
            return [self._invalid("Invalid party slot!")]
        chosen = party.creatures[party_index]
        if chosen is self._active:
            return [self._invalid(f"{chosen.name} is already in battle!")]
        if chosen.is_fainted:
            return [self._invalid(f"{chosen.name} has no energy left to battle!")]

        forced = self._state is BattleState.SELECTING_SWITCH
        party.swap(0, party_index)
        self._active = chosen
        chosen.reset_battle_stages()
        self._state = BattleState.SELECTING_ACTION
        events = [BattleEvent(EventType.CREATURE_SENT, f"Go! {chosen.name}!",
                              {"creature": chosen.name, "uid": chosen.uid})]
        if not forced:
            self._turn_count += 1
            events += self._opponent_free_attack()
        return events

    def learn_pending_move(self, forget_slot: Optional[int]) -> List[BattleEvent]:
        """Answer the "forget a move?" question. ``None`` means don't learn the new move."""
        if not self._pending_moves:
            return []
        learner, move = self._pending_moves.pop(0)
        if forget_slot is not None and 0 <= forget_slot < len(learner.moves):
            forgotten = learner.moves[forget_slot].name
            learner.learn_move(move, slot=forget_slot)
            return [BattleEvent(EventType.MOVE_LEARNED,
                                f"{learner.name} forgot {forgotten} and learned {move.name}!",
                                {"uid": learner.uid, "move": move.name})]
        return [BattleEvent(EventType.MOVE_NOT_LEARNED, f"{learner.name} did not learn {move.name}.",
                            {"uid": learner.uid, "move": move.name})]

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

    def _check_can_act(self) -> List[BattleEvent]:
        """Events explaining why the player can't act right now (empty if they can)."""
        if not self.is_active:
            return [self._invalid("The battle is over!")]
        if self._active is None:
            self._state = BattleState.LOST
            return [BattleEvent(EventType.BATTLE_LOST, "You have no creatures that can fight!")]
        if self._state is BattleState.SELECTING_SWITCH:
            return [self._invalid("Choose a creature to send out!")]
        return []

    def _turn_over(self) -> bool:
        return not self.is_active or self._state is BattleState.SELECTING_SWITCH

    def _opponent_moves_first(self, mine: Creature) -> bool:
        if mine.speed != self._opponent.speed:
            return self._opponent.speed > mine.speed
        return random.random() < 0.5

    def _opponent_free_attack(self) -> List[BattleEvent]:
        """The opponent attacks after the player spends a turn on something else."""
        mine = self._active
        if mine is None or mine.is_fainted or self._opponent.is_fainted:
            return []
        move = self._ai.choose_move(self._opponent, mine)
        events = self._execute_move_step(self._opponent, mine, move)
        events += self._resolve_faints()
        if not self._turn_over():
            events += self._end_of_turn()
        return events

    @staticmethod
    def _hp_data(creature: Creature) -> dict:
        return {"target": creature.name, "target_uid": creature.uid,
                "target_current_hp": creature.current_hp, "target_max_hp": creature.max_hp}

    @staticmethod
    def _fainted_event(creature: Creature) -> BattleEvent:
        return BattleEvent(EventType.FAINTED, f"{creature.name} fainted!",
                           {"fainted": creature.name, "uid": creature.uid})

    def _execute_move_step(self, user: Creature, target: Creature, move: Move) -> List[BattleEvent]:
        """One creature uses one move."""
        events: List[BattleEvent] = []

        if user.status:
            can_act, message = user.status.before_move(user)
            if message:
                kind = EventType.STATUS_HINDRANCE if not can_act else EventType.STATUS_CURED
                events.append(BattleEvent(kind, message, {"creature": user.name, "uid": user.uid}))
            if not can_act:
                return events

        move.use()
        events.append(BattleEvent(EventType.MOVE_USED, f"{user.name} used {move.name}!",
                                  {"user": user.name, "user_uid": user.uid,
                                   "move": move.name, "type": move.type}))

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
            events.append(BattleEvent(EventType.DAMAGE_DEALT, f"{target.name} took {lost} damage!",
                                      {**self._hp_data(target), "damage": lost}))
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
            # Effects like Recover change HP: tell the UI the new values.
            if any(e.event_type is EventType.HEAL for e in effect_events):
                events.append(BattleEvent(EventType.HEAL, "", self._hp_data(user)))

        if target.is_fainted:
            events.append(self._fainted_event(target))
        return events

    def _end_of_turn(self) -> List[BattleEvent]:
        """Status damage for both sides, then check for faints."""
        events: List[BattleEvent] = []
        for creature in (self._active, self._opponent):
            if creature is None or creature.is_fainted or not creature.status:
                continue
            status_key = creature.status.key
            damage, message = creature.status.on_turn_end(creature)
            if damage <= 0:
                continue
            creature.take_damage(damage)
            events.append(BattleEvent(EventType.STATUS_DAMAGE, message,
                                      {**self._hp_data(creature), "creature": creature.name,
                                       "damage": damage, "status": status_key}))
            if creature.is_fainted:
                events.append(self._fainted_event(creature))
        return events + self._resolve_faints()

    def _resolve_faints(self) -> List[BattleEvent]:
        """After damage: decide whether the battle is won, lost, or needs a switch."""
        mine = self._active
        events: List[BattleEvent] = []
        if self._opponent.is_fainted:
            events += self._award_victory_xp(mine)
            events += self._on_opponent_fainted()   # polymorphic: wild vs trainer
            if not self.is_active:
                return events
        if mine is not None and mine.is_fainted:
            if self._player.party.all_fainted():
                self._state = BattleState.LOST
                return [BattleEvent(EventType.BATTLE_LOST,
                                    f"{self._player.name} is out of usable creatures! You blacked out!")]
            self._state = BattleState.SELECTING_SWITCH
            return events + [BattleEvent(EventType.CHOOSE_NEXT, "Choose the next creature!")]
        return events

    def _award_victory_xp(self, winner: Optional[Creature]) -> List[BattleEvent]:
        if winner is None or winner.is_fainted:
            return []
        foe = self._opponent
        xp = max(1, int(foe.base_xp * foe.level / 7 * self._xp_multiplier))
        events = [BattleEvent(EventType.XP_GAINED, f"{winner.name} gained {xp} EXP. Points!",
                              {"creature": winner.name, "uid": winner.uid, "xp": xp})]
        result = winner.gain_xp(xp)
        if result["leveled_up"]:
            events.append(BattleEvent(EventType.LEVEL_UP,
                                      f"{winner.name} grew to level {result['new_level']}!",
                                      {**result, "uid": winner.uid}))
            for move_id in result["unlocked_moves"]:
                events += self._offer_move(winner, move_id)
        return events

    def _offer_move(self, learner: Creature, move_id: str) -> List[BattleEvent]:
        """Teach a newly unlocked move, or queue a "forget which move?" question."""
        if self._move_source is None:
            return [BattleEvent(EventType.UNLOCKED_MOVE,
                                f"{learner.name} can learn a new move ({move_id})!",
                                {"move_id": move_id})]
        if learner.knows_move(move_id):
            return []
        move = self._move_source(move_id)
        if learner.learn_move(move):
            return [BattleEvent(EventType.MOVE_LEARNED, f"{learner.name} learned {move.name}!",
                                {"uid": learner.uid, "move": move.name})]
        self._pending_moves.append((learner, move))
        return [BattleEvent(EventType.LEARN_MOVE_PROMPT,
                            f"{learner.name} wants to learn {move.name}, but already knows 4 moves.",
                            {"uid": learner.uid, "move": move.name})]


class WildBattle(Battle):
    """A battle against a wild creature: you can run away or try to catch it."""

    @property
    def wild_creature(self) -> Creature:
        return self._opponent

    @property
    def can_flee(self) -> bool:
        return True

    @property
    def can_catch(self) -> bool:
        return True

    @property
    def intro_message(self) -> str:
        return f"Wild {self._opponent.name} appeared!"

    def _on_opponent_fainted(self) -> List[BattleEvent]:
        self._state = BattleState.WON
        return [BattleEvent(EventType.BATTLE_WON, f"Defeated wild {self._opponent.name}!")]


class TrainerBattle(Battle):
    """A battle against another trainer's team, one creature at a time."""

    def __init__(
        self,
        player: Trainer,
        opponent_party: Sequence[Creature],
        type_chart: TypeChart,
        trainer_name: str,
        trainer_title: str = "TRAINER",
        prize: int = 0,
        defeat_lines: Iterable[str] = (),
        flags=None,
        defeat_flag: Optional[str] = None,
        ai: Optional[BattleAI] = None,
        move_source: Optional[MoveSource] = None,
    ):
        if not opponent_party:
            raise ValueError("A trainer needs at least one creature")
        super().__init__(player, opponent_party[0], type_chart, ai, move_source)
        self._reserve: List[Creature] = list(opponent_party[1:])
        self._trainer_name = trainer_name
        self._trainer_title = trainer_title
        self._prize = prize
        self._defeat_lines = tuple(defeat_lines)
        self._flags = flags
        self._defeat_flag = defeat_flag

    @property
    def trainer_name(self) -> str:
        return self._trainer_name

    @property
    def defeat_lines(self) -> Tuple[str, ...]:
        """What the trainer says after losing (shown in the overworld)."""
        return self._defeat_lines

    @property
    def after_battle_lines(self) -> Tuple[str, ...]:
        return self._defeat_lines if self._state is BattleState.WON else ()

    @property
    def remaining(self) -> int:
        """Creatures the trainer still has, including the one out now."""
        return len(self._reserve) + (0 if self._opponent.is_fainted else 1)

    @property
    def can_flee(self) -> bool:
        return False

    @property
    def can_catch(self) -> bool:
        return False

    @property
    def intro_message(self) -> str:
        who = f"{self._trainer_title} {self._trainer_name}"
        return f"{who} wants to battle! {self._trainer_name} sent out {self._opponent.name}!"

    @property
    def _xp_multiplier(self) -> float:
        return 1.5

    def _on_opponent_fainted(self) -> List[BattleEvent]:
        if self._reserve:
            self._opponent = self._reserve.pop(0)
            self._opponent.reset_battle_stages()
            return [BattleEvent(EventType.OPPONENT_SENT,
                                f"{self._trainer_name} sent out {self._opponent.name}!",
                                {"uid": self._opponent.uid, "species_id": self._opponent.species_id})]
        self._state = BattleState.WON
        events = [BattleEvent(EventType.BATTLE_WON,
                              f"You defeated {self._trainer_title} {self._trainer_name}!")]
        if self._prize > 0:
            self._player.earn(self._prize)
            events.append(BattleEvent(EventType.PRIZE_MONEY, f"You got ${self._prize} for winning!",
                                      {"amount": self._prize}))
        if self._flags is not None and self._defeat_flag:
            self._flags.set(self._defeat_flag)
        return events + self._victory_extras()

    def _victory_extras(self) -> List[BattleEvent]:
        """Anything extra on winning (GymBattle adds a badge)."""
        return []


class GymBattle(TrainerBattle):
    """A gym leader battle: winning also earns the gym's badge."""

    def __init__(self, *args, badge: str, badge_case, **kwargs):
        super().__init__(*args, **kwargs)
        self._badge = badge
        self._badge_case = badge_case

    @property
    def badge(self) -> str:
        return self._badge

    def _victory_extras(self) -> List[BattleEvent]:
        if not self._badge_case.add(self._badge):
            return []
        return [BattleEvent(EventType.BADGE_EARNED,
                            f"{self._player.name} received the {self._badge}!",
                            {"badge": self._badge})]
