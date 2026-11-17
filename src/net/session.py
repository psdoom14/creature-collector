"""Link battle sessions: what the battle screen talks to instead of a local Battle.

    LinkSession (abstract)    submit(action), poll() -> events, must_switch, waiting, error
    ├── HostSession           runs the LinkBattle; resolves a turn once both actions are in,
    │                         plays the events locally and sends them to the guest
    └── GuestSession          sends its action; plays back the events the host sends,
                              keeping a mirror of both teams up to date (GuestView)

``HostLobby`` / ``GuestLobby`` do the hello/welcome handshake and then hand over a session.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from src.model.battle import BattleState
from src.model.events import BattleEvent, EventType
from src.model.link_battle import LINK_LEVEL, SIDE_A, SIDE_B, LinkAction, LinkBattle, build_link_team
from src.model.trainer import Trainer
from src.net.connection import Connection, ConnectionLost
from src.net.protocol import PROTOCOL_VERSION, IdMap, data_fingerprint, decode_events, encode_events

HP_EVENTS = (EventType.DAMAGE_DEALT, EventType.STATUS_DAMAGE, EventType.HEAL, EventType.ITEM_USED)


class LinkSession(ABC):
    """One player's end of a link battle."""

    my_side: str = SIDE_A

    def __init__(self, conn: Connection, opponent_name: str):
        self._conn = conn
        self.opponent_name = opponent_name
        self.error: Optional[str] = None

    @property
    @abstractmethod
    def view(self):
        """The battle as this player sees it (what the battle screen draws)."""

    @abstractmethod
    def submit(self, action: LinkAction) -> None:
        """This player's choice for the turn (results arrive through ``poll``)."""

    @abstractmethod
    def poll(self) -> List[BattleEvent]:
        """Events that are ready to play (empty while waiting)."""

    @property
    @abstractmethod
    def must_switch(self) -> bool:
        """This player's creature fainted and they must choose the next one."""

    @property
    @abstractmethod
    def waiting(self) -> bool:
        """Nothing for this player to do until the other player acts."""

    @property
    def finished(self) -> bool:
        return not self.view.is_active

    def _send(self, message: dict) -> None:
        try:
            self._conn.send(message)
        except ConnectionLost:
            self.error = f"Lost the connection to {self.opponent_name}."

    def _check_connection(self) -> None:
        if self.error is None and self._conn.closed and not self.finished:
            self.error = f"Lost the connection to {self.opponent_name}."

    def close(self) -> None:
        if not self._conn.closed:
            self._send({"type": "bye"})
        self._conn.close()


class HostSession(LinkSession):
    my_side = SIDE_A

    def __init__(self, conn: Connection, battle: LinkBattle, opponent_name: str):
        super().__init__(conn, opponent_name)
        self.battle = battle
        self._ids = IdMap(battle.trainer(SIDE_A).party.creatures, battle.trainer(SIDE_B).party.creatures)
        self._pending: Dict[str, LinkAction] = {}
        self._ready: List[BattleEvent] = []

    @property
    def view(self):
        return self.battle

    @property
    def must_switch(self) -> bool:
        return SIDE_A in self.battle.needs_switch

    @property
    def waiting(self) -> bool:
        expected = self.battle.expected_sides()
        return bool(expected) and (SIDE_A in self._pending or SIDE_A not in expected)

    def submit(self, action: LinkAction) -> None:
        if SIDE_A in self.battle.expected_sides():
            self._pending[SIDE_A] = action
            self._try_resolve()

    def poll(self) -> List[BattleEvent]:
        for message in self._conn.poll():
            kind = message.get("type")
            if kind == "action" and SIDE_B in self.battle.expected_sides():
                self._pending[SIDE_B] = LinkAction.from_dict(message.get("action", {}))
            elif kind == "bye" and not self.finished:
                self.error = f"{self.opponent_name} left the battle."
        self._try_resolve()
        self._check_connection()
        ready, self._ready = self._ready, []
        return ready

    def _try_resolve(self) -> None:
        expected = self.battle.expected_sides()
        if expected and expected <= set(self._pending):
            events = self.battle.resolve({side: self._pending[side] for side in expected})
            self._pending.clear()
            self._send({"type": "events", "events": encode_events(events, self._ids),
                        "needs": sorted(self.battle.needs_switch)})
            self._ready.extend(events)


class GuestView:
    """The guest's picture of the battle: mirror copies of both teams, updated from the host's events.

    Offers the same read-only properties the battle screen uses on a real Battle.
    """
    can_flee = False
    can_catch = False
    pending_move = None
    pending_learner = None
    after_battle_lines = ()

    def __init__(self, me: Trainer, host: Trainer):
        self.player = me
        self._host = host
        self._active = me.party.creatures[0]
        self._opponent = host.party.creatures[0]
        self._state = BattleState.SELECTING_ACTION
        self._by_uid = {c.uid: c for c in list(me.party) + list(host.party)}

    @property
    def player_creature(self):
        return self._active

    @property
    def opponent(self):
        return self._opponent

    @property
    def state(self) -> BattleState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state in (BattleState.SELECTING_ACTION, BattleState.SELECTING_SWITCH)

    @property
    def intro_message(self) -> str:
        return f"{self._host.name} wants to battle! {self._host.name} sent out {self._opponent.name}!"

    @staticmethod
    def _set_hp(creature, hp: int) -> None:
        difference = creature.current_hp - hp
        if difference > 0:
            creature.take_damage(difference)
        elif difference < 0:
            creature.heal(-difference)

    def apply(self, event: BattleEvent) -> None:
        """Bring the mirror teams up to date with one event from the host."""
        kind, data = event.event_type, event.data
        if kind in HP_EVENTS and data.get("target_uid") in self._by_uid:
            self._set_hp(self._by_uid[data["target_uid"]], data["target_current_hp"])
        elif kind is EventType.FAINTED and data.get("uid") in self._by_uid:
            creature = self._by_uid[data["uid"]]
            if not creature.is_fainted:
                creature.take_damage(creature.current_hp)
        elif kind is EventType.MOVE_USED and data.get("user_uid") in self._by_uid:
            for move in self._by_uid[data["user_uid"]].moves:
                if move.name == data.get("move"):
                    move.use()
                    break
        elif kind is EventType.STATUS_APPLIED and data.get("target_uid") in self._by_uid:
            self._by_uid[data["target_uid"]].apply_status(data["status"])
        elif kind is EventType.STATUS_CURED and data.get("uid") in self._by_uid:
            self._by_uid[data["uid"]].cure_status()
        elif kind is EventType.STAT_CHANGE and data.get("target_uid") in self._by_uid:
            self._by_uid[data["target_uid"]].modify_stat_stage(data["stat"], data["change"])
        elif kind is EventType.CREATURE_SENT and data.get("uid") in self._by_uid:
            self._active = self._bring_out(self.player, data["uid"])
        elif kind is EventType.OPPONENT_SENT and data.get("uid") in self._by_uid:
            self._opponent = self._bring_out(self._host, data["uid"])
        elif kind is EventType.BATTLE_WON:
            self._state = BattleState.WON
        elif kind is EventType.BATTLE_LOST:
            self._state = BattleState.LOST

    def _bring_out(self, trainer: Trainer, uid):
        creature = self._by_uid[uid]
        trainer.party.swap(0, trainer.party.creatures.index(creature))
        creature.reset_battle_stages()
        return creature


class GuestSession(LinkSession):
    my_side = SIDE_B

    def __init__(self, conn: Connection, view: GuestView, host_team: Sequence, my_team: Sequence,
                 opponent_name: str):
        super().__init__(conn, opponent_name)
        self._view = view
        self._ids = IdMap(host_team, my_team)
        self._needs: set = set()
        self._submitted = False

    @property
    def view(self):
        return self._view

    @property
    def must_switch(self) -> bool:
        return SIDE_B in self._needs

    @property
    def waiting(self) -> bool:
        if self.finished:
            return False
        return self._submitted or (bool(self._needs) and SIDE_B not in self._needs)

    def submit(self, action: LinkAction) -> None:
        self._submitted = True
        self._send({"type": "action", "action": action.to_dict()})

    def poll(self) -> List[BattleEvent]:
        events: List[BattleEvent] = []
        for message in self._conn.poll():
            kind = message.get("type")
            if kind == "events":
                batch = decode_events(message.get("events", []), self._ids, flip=True)
                for event in batch:
                    self._view.apply(event)
                events += batch
                self._needs = set(message.get("needs", []))
                self._submitted = False
            elif kind == "bye" and not self.finished:
                self.error = f"{self.opponent_name} left the battle."
        self._check_connection()
        return events


# ----------------------------------------------------------------------
# Handshake
# ----------------------------------------------------------------------
class LinkRejected(Exception):
    """The other game refused the link (different version, empty team...)."""


class _Lobby:
    def __init__(self, conn: Connection, name: str, species: Sequence[int], loader):
        if not species:
            raise LinkRejected("You need at least one creature to battle.")
        self.conn = conn
        self.name = name
        self.species = list(species)[:6]
        self.loader = loader
        self.fingerprint = data_fingerprint(Path(loader.data_dir))


class HostLobby(_Lobby):
    """Waits for the guest's hello, checks it, answers, and starts the battle."""

    def poll(self) -> Optional[HostSession]:
        for message in self.conn.poll():
            if message.get("type") != "hello":
                continue
            if message.get("protocol") != PROTOCOL_VERSION or message.get("data") != self.fingerprint:
                self.conn.send({"type": "reject", "reason": "The two games are different versions."})
                raise LinkRejected("Your friend's game is a different version.")
            guest_species = [int(s) for s in message.get("team", [])][:6]
            if not guest_species:
                self.conn.send({"type": "reject", "reason": "Your team is empty."})
                raise LinkRejected("Your friend has no creatures.")
            self.conn.send({"type": "welcome", "name": self.name, "team": self.species, "level": LINK_LEVEL})
            host = Trainer(self.name, build_link_team(self.loader, self.species))
            guest = Trainer(message.get("name", "FRIEND")[:8], build_link_team(self.loader, guest_species))
            return HostSession(self.conn, LinkBattle(host, guest, self.loader.get_type_chart()), guest.name)
        if self.conn.closed:
            raise LinkRejected("Your friend disconnected.")
        return None


class GuestLobby(_Lobby):
    """Says hello and waits for the host's welcome."""

    def __init__(self, conn: Connection, name: str, species: Sequence[int], loader):
        super().__init__(conn, name, species, loader)
        conn.send({"type": "hello", "protocol": PROTOCOL_VERSION, "data": self.fingerprint,
                   "name": name, "team": self.species})

    def poll(self) -> Optional[GuestSession]:
        for message in self.conn.poll():
            if message.get("type") == "reject":
                raise LinkRejected(message.get("reason", "The host refused the link."))
            if message.get("type") == "welcome":
                host_name = message.get("name", "HOST")[:8]
                host_team = build_link_team(self.loader, message.get("team", []))
                my_team = build_link_team(self.loader, self.species)
                me, host = Trainer(self.name, my_team), Trainer(host_name, host_team)
                view = GuestView(me, host)
                return GuestSession(self.conn, view, host_team.creatures, my_team.creatures, host_name)
        if self.conn.closed:
            raise LinkRejected("Lost the connection to the host.")
        return None
