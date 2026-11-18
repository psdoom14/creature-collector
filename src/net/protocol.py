"""What the two games say to each other.

Messages (one JSON object each):
    guest -> host  {"type": "hello",   "protocol", "data", "name", "team": [species ids]}
    host -> guest  {"type": "welcome", "name", "team", "level"}  or  {"type": "reject", "reason"}
    guest -> host  {"type": "action",  "action": {"kind", "index"}}
    host -> guest  {"type": "events",  "events": [...], "needs": ["A"|"B", ...]}
    either         {"type": "bye"}

Creatures are named by **link ids** ("A0" = host's first creature, "B2" = guest's
third) because each computer gives its own objects different ``uid`` numbers.
The guest also sees every event from its own side, so a few event types are
flipped (the host's "creature sent" is the guest's "opponent sent").
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List

from src.model.events import BattleEvent, EventType

PROTOCOL_VERSION = 1
DATA_FILES = ("creatures.json", "moves.json", "items.json", "type_chart.json")

# The same event, seen from the other player's side
FLIPPED = {
    EventType.CREATURE_SENT: EventType.OPPONENT_SENT,
    EventType.OPPONENT_SENT: EventType.CREATURE_SENT,
    EventType.BATTLE_WON: EventType.BATTLE_LOST,
    EventType.BATTLE_LOST: EventType.BATTLE_WON,
}


def data_fingerprint(data_dir: Path) -> str:
    """A short hash of the game data; both players must match or results would differ.

    It hashes the data's *content*, not the file bytes, so the same data gives the same
    fingerprint on every computer (Git on Windows usually rewrites line endings, which
    changes the bytes but not the data).
    """
    digest = hashlib.sha256(str(PROTOCOL_VERSION).encode())
    for name in DATA_FILES:
        with open(Path(data_dir) / name, encoding="utf-8") as f:
            content = json.load(f)
        digest.update(json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()[:16]


class IdMap:
    """Translates between this computer's creature uids and the shared link ids."""

    def __init__(self, team_a: Iterable, team_b: Iterable):
        self._to_link: Dict[int, str] = {}
        self._to_uid: Dict[str, int] = {}
        for prefix, team in (("A", team_a), ("B", team_b)):
            for i, creature in enumerate(team):
                link_id = f"{prefix}{i}"
                self._to_link[creature.uid] = link_id
                self._to_uid[link_id] = creature.uid

    def link_id(self, uid):
        return self._to_link.get(uid, uid)

    def uid(self, link_id):
        return self._to_uid.get(link_id, link_id)


def _map_ids(data: dict, convert) -> dict:
    return {k: (convert(v) if k.endswith("uid") else v) for k, v in data.items()}


def encode_events(events: List[BattleEvent], ids: IdMap) -> List[dict]:
    """Host side: events -> JSON-able dicts with link ids."""
    out = []
    for e in events:
        data = {k: v for k, v in e.data.items() if k != "creature" or isinstance(v, str)}
        out.append({"type": e.event_type.value, "message": e.message,
                    "data": _map_ids(data, ids.link_id)})
    return out


def decode_events(items: List[dict], ids: IdMap, flip: bool) -> List[BattleEvent]:
    """Guest side: dicts -> events with this computer's uids, seen from this player's side."""
    events = []
    for item in items:
        kind = EventType(item["type"])
        if flip:
            kind = FLIPPED.get(kind, kind)
        events.append(BattleEvent(kind, item.get("message", ""), _map_ids(item.get("data", {}), ids.uid)))
    return events
