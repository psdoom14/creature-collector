"""Link battles: two human players, each choosing their own actions every turn.

``LinkBattle`` reuses everything in ``Battle`` that doesn't care who is choosing
(damage, statuses, move effects, faint events) and replaces the turn flow: instead
of an AI picking the opponent's move, both players submit a ``LinkAction`` and the
turn is resolved once both have arrived.

Side A is the host's team, side B the guest's. Only the host's computer runs this
class; the guest's game plays back the events the host sends (see ``src/net``).
"""
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from src.model.battle import Battle, BattleState
from src.model.creature import Creature
from src.model.errors import GameDataError, RuleViolation
from src.model.events import BattleEvent, EventType
from src.model.move import Move, MoveFactory
from src.model.trainer import Party, Trainer
from src.model.type_chart import TypeChart

SIDE_A = "A"
SIDE_B = "B"
LINK_LEVEL = 50          # every creature fights at this level in a link battle
MAX_TEAM = 6


def other_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A


def build_link_team(loader, species_ids: Iterable[int], level: int = LINK_LEVEL) -> Party:
    """A fresh team for a link battle: every species at ``level``, full HP, level-``level`` moves.

    Both computers call this with the same species list and get identical creatures,
    so neither the player's own creatures nor their save are touched.
    """
    return Party([loader.get_creature(int(sid), level=level) for sid in list(species_ids)[:MAX_TEAM]])


@dataclass(frozen=True)
class LinkAction:
    """What one player chose this turn (the Command pattern: an action as an object)."""
    kind: str          # "move", "switch" or "forfeit"
    index: int = 0

    KINDS = ("move", "switch", "forfeit")

    @classmethod
    def move(cls, index: int) -> "LinkAction":
        return cls("move", index)

    @classmethod
    def switch(cls, index: int) -> "LinkAction":
        return cls("switch", index)

    @classmethod
    def forfeit(cls) -> "LinkAction":
        return cls("forfeit")

    def to_dict(self) -> Dict:
        return {"kind": self.kind, "index": self.index}

    @classmethod
    def from_dict(cls, data: Dict) -> "LinkAction":
        kind = data.get("kind")
        if kind not in cls.KINDS:
            raise GameDataError(f"Unknown link action '{kind}'")
        return cls(kind, int(data.get("index", 0)))


class LinkBattle(Battle):
    """A battle between two players' teams, both controlled by people."""

    def __init__(self, trainer_a: Trainer, trainer_b: Trainer, type_chart: TypeChart):
        if trainer_a.party.size == 0 or trainer_b.party.size == 0:
            raise RuleViolation("Both players need at least one creature")
        super().__init__(trainer_a, trainer_b.party.creatures[0], type_chart)
        self._trainer_b = trainer_b
        self._needs_switch: Set[str] = set()
        self._winner: Optional[str] = None

    # --- hooks required by Battle ---------------------------------------
    @property
    def can_flee(self) -> bool:
        return False

    @property
    def can_catch(self) -> bool:
        return False

    @property
    def intro_message(self) -> str:
        b = self._trainer_b
        return f"{b.name} wants to battle! {b.name} sent out {self._opponent.name}!"

    def _on_opponent_fainted(self) -> List[BattleEvent]:
        return []  # faints are handled by _check_faints for both sides

    # --- read-only state -------------------------------------------------
    @property
    def needs_switch(self) -> Set[str]:
        """Sides whose creature fainted and who must choose a replacement before the next turn."""
        return set(self._needs_switch)

    @property
    def winner(self) -> Optional[str]:
        return self._winner

    def trainer(self, side: str) -> Trainer:
        return self._player if side == SIDE_A else self._trainer_b

    def active(self, side: str) -> Creature:
        return self._active if side == SIDE_A else self._opponent

    def expected_sides(self) -> Set[str]:
        """Who has to submit an action before ``resolve`` can run."""
        if not self.is_active:
            return set()
        return set(self._needs_switch) or {SIDE_A, SIDE_B}

    # --- the turn ----------------------------------------------------------
    def resolve(self, actions: Dict[str, LinkAction]) -> List[BattleEvent]:
        """Play one turn (or the replacement switches after a faint) from both players' choices."""
        expected = self.expected_sides()
        if set(actions) != expected:
            raise RuleViolation(f"Waiting for actions from {sorted(expected)}, got {sorted(actions)}")

        if self._needs_switch:
            events: List[BattleEvent] = []
            for side in sorted(self._needs_switch):
                events += self._switch(side, actions[side])
            self._needs_switch.clear()
            return events

        for side in (SIDE_A, SIDE_B):
            if actions[side].kind == "forfeit":
                name = self.trainer(side).name
                return [BattleEvent(EventType.INVALID_ACTION, f"{name} forfeited the battle!")] \
                    + self._finish(other_side(side))

        self._turn_count += 1
        events = []
        for side in (SIDE_A, SIDE_B):           # switching always goes before attacks
            if actions[side].kind == "switch":
                events += self._switch(side, actions[side])

        movers = [s for s in (SIDE_A, SIDE_B) if actions[s].kind == "move"]
        movers.sort(key=lambda s: self._speed_key(s), reverse=True)
        for side in movers:
            attacker, defender = self.active(side), self.active(other_side(side))
            if attacker.is_fainted or defender.is_fainted:
                continue
            events += self._execute_move_step(attacker, defender, self._pick_move(attacker, actions[side].index))

        events += self._status_damage()
        return events + self._check_faints()

    # --- helpers -------------------------------------------------------------
    def _speed_key(self, side: str):
        return (self.active(side).speed, random.random())   # ties broken at random

    @staticmethod
    def _pick_move(creature: Creature, index: int) -> Move:
        moves = creature.moves
        if 0 <= index < len(moves) and moves[index].can_use():
            return moves[index]
        usable = [m for m in moves if m.can_use()]
        return usable[0] if usable else MoveFactory.struggle()

    def _switch(self, side: str, action: LinkAction) -> List[BattleEvent]:
        if action.kind != "switch":
            raise RuleViolation(f"Side {side} must choose a creature to send out")
        party = self.trainer(side).party
        if not 0 <= action.index < party.size:
            raise RuleViolation("Invalid party slot")
        chosen = party.creatures[action.index]
        if chosen.is_fainted or chosen is self.active(side):
            raise RuleViolation(f"{chosen.name} can't be sent out")
        party.swap(0, action.index)
        chosen.reset_battle_stages()
        if side == SIDE_A:
            self._active = chosen
        else:
            self._opponent = chosen
        kind = EventType.CREATURE_SENT if side == SIDE_A else EventType.OPPONENT_SENT
        return [BattleEvent(kind, f"{self.trainer(side).name} sent out {chosen.name}!",
                            {"creature": chosen.name, "uid": chosen.uid, "side": side})]

    def _status_damage(self) -> List[BattleEvent]:
        events: List[BattleEvent] = []
        for side in (SIDE_A, SIDE_B):
            creature = self.active(side)
            if creature.is_fainted or not creature.status:
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
        return events

    def _check_faints(self) -> List[BattleEvent]:
        wiped = [s for s in (SIDE_A, SIDE_B) if self.trainer(s).party.all_fainted()]
        if wiped:
            return self._finish(None if len(wiped) == 2 else other_side(wiped[0]))
        events: List[BattleEvent] = []
        for side in (SIDE_A, SIDE_B):
            if self.active(side).is_fainted:
                self._needs_switch.add(side)
                events.append(BattleEvent(EventType.CHOOSE_NEXT,
                                          f"{self.trainer(side).name} is choosing the next creature...",
                                          {"side": side}))
        return events

    def _finish(self, winner: Optional[str]) -> List[BattleEvent]:
        self._winner = winner
        self._needs_switch.clear()
        if winner is None:
            self._state = BattleState.LOST
            return [BattleEvent(EventType.BATTLE_LOST, "It's a draw!", {"winner": None})]
        self._state = BattleState.WON if winner == SIDE_A else BattleState.LOST
        kind = EventType.BATTLE_WON if winner == SIDE_A else EventType.BATTLE_LOST
        return [BattleEvent(kind, f"{self.trainer(winner).name} won the battle!", {"winner": winner})]
