"""The overworld: maps made of tiles, warps between maps, and the player's position.

All movement rules live here (what blocks you, where warps go, where wild
creatures appear), so the overworld screen only has to animate and draw.
"""
import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.model.direction import Direction
from src.model.entities import Interactable, Interaction

__all__ = ["Direction", "Location", "TileKind", "TILE_KINDS", "Warp", "WorldMap", "World",
           "Explorer", "StepResult"]


@dataclass(frozen=True)
class Location:
    """A tile on a specific map."""
    map_id: str
    x: int
    y: int

    def moved(self, direction: Direction) -> "Location":
        return Location(self.map_id, self.x + direction.dx, self.y + direction.dy)

    def to_dict(self) -> Dict[str, Any]:
        return {"map": self.map_id, "x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        return cls(data["map"], int(data["x"]), int(data["y"]))


@dataclass(frozen=True)
class TileKind:
    """What a kind of tile does. The UI decides how it looks."""
    name: str
    walkable: bool
    encounters: bool = False      # wild creatures can appear here
    talk_through: bool = False    # you can talk to someone standing behind it (shop counters)


def _kinds(*kinds: TileKind) -> Dict[str, TileKind]:
    return {k.name: k for k in kinds}


TILE_KINDS: Dict[str, TileKind] = _kinds(
    # Outdoors
    TileKind("grass", True), TileKind("path", True), TileKind("flowers", True),
    TileKind("tall_grass", True, encounters=True),
    TileKind("tree", False), TileKind("water", False), TileKind("fence", False),
    # Buildings (doors only become passable when a warp is placed on them)
    TileKind("house_roof", False), TileKind("house_wall", False), TileKind("house_window", False),
    TileKind("house_door", False),
    TileKind("center_roof", False), TileKind("center_sign", False), TileKind("center_wall", False),
    TileKind("center_door", False),
    TileKind("gym_roof", False), TileKind("gym_wall", False), TileKind("gym_door", False),
    # Indoors
    TileKind("floor", True), TileKind("mat", True), TileKind("wall", False),
    TileKind("counter", False, talk_through=True), TileKind("machine", False),
    TileKind("plant", False), TileKind("pc", False), TileKind("table", False),
    TileKind("bookshelf", False),
)


@dataclass(frozen=True)
class Warp:
    """Stepping on (x, y) moves the player to ``target``, facing ``facing``.

    If ``required_flag`` is set, the warp only works once that story flag is set;
    until then the player is stopped and shown ``blocked_lines``.
    """
    x: int
    y: int
    target: Location
    facing: Direction
    required_flag: Optional[str] = None
    blocked_lines: Tuple[str, ...] = ()


class WorldMap:
    """One map: a grid of tiles plus warps, entities and an optional encounter table."""

    def __init__(self, map_id: str, name: str, tiles: List[List[str]], warps: Iterable[Warp] = (),
                 entities: Iterable[Interactable] = (), encounter_table: Optional[str] = None,
                 encounter_rate: float = 0.0):
        if not tiles or any(len(row) != len(tiles[0]) for row in tiles):
            raise ValueError(f"Map '{map_id}' rows must all be the same length")
        for row in tiles:
            for name_ in row:
                if name_ not in TILE_KINDS:
                    raise ValueError(f"Map '{map_id}' uses unknown tile '{name_}'")
        self._id = map_id
        self._name = name
        self._tiles = [list(row) for row in tiles]
        self._warps: Dict[Tuple[int, int], Warp] = {(w.x, w.y): w for w in warps}
        self._entities: List[Interactable] = list(entities)
        self._encounter_table = encounter_table
        self._encounter_rate = encounter_rate

    # --- read-only data ------------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return len(self._tiles[0])

    @property
    def height(self) -> int:
        return len(self._tiles)

    @property
    def warps(self) -> Tuple[Warp, ...]:
        return tuple(self._warps.values())

    @property
    def entities(self) -> Tuple[Interactable, ...]:
        return tuple(self._entities)

    @property
    def encounter_table(self) -> Optional[str]:
        return self._encounter_table

    @property
    def encounter_rate(self) -> float:
        return self._encounter_rate

    # --- queries -------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_name(self, x: int, y: int) -> str:
        return self._tiles[y][x]

    def tile_at(self, x: int, y: int) -> TileKind:
        return TILE_KINDS[self._tiles[y][x]]

    def warp_at(self, x: int, y: int) -> Optional[Warp]:
        return self._warps.get((x, y))

    def entity_at(self, x: int, y: int) -> Optional[Interactable]:
        return next((e for e in self._entities if e.position == (x, y)), None)

    def is_passable(self, x: int, y: int) -> bool:
        """Can the player stand on (x, y)? Warps make doors passable; entities block."""
        if not self.in_bounds(x, y):
            return False
        entity = self.entity_at(x, y)
        if entity is not None and entity.blocks_movement:
            return False
        return self.tile_at(x, y).walkable or (x, y) in self._warps

    # --- loading -------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldMap":
        """Build a map from its JSON description (``legend`` maps characters to tile names)."""
        legend: Dict[str, str] = data["legend"]
        tiles = []
        for y, row in enumerate(data["rows"]):
            tile_row = []
            for x, ch in enumerate(row):
                if ch not in legend:
                    raise ValueError(f"Map '{data['id']}' has unknown character {ch!r} at ({x}, {y})")
                tile_row.append(legend[ch])
            tiles.append(tile_row)
        warps = [Warp(w["x"], w["y"], Location(w["to"], w["tx"], w["ty"]),
                      Direction.from_name(w.get("facing", "down")),
                      w.get("requires"), tuple(w.get("blocked_lines", ())))
                 for w in data.get("warps", [])]
        entities = [Interactable.from_data(e) for e in data.get("entities", [])]
        return cls(data["id"], data["name"], tiles, warps, entities,
                   data.get("encounters"), data.get("encounter_rate", 0.0))


class World:
    """All maps, looked up by id."""

    def __init__(self, maps: Iterable[WorldMap]):
        self._maps: Dict[str, WorldMap] = {m.id: m for m in maps}

    @property
    def maps(self) -> Tuple[WorldMap, ...]:
        return tuple(self._maps.values())

    @property
    def map_ids(self) -> Tuple[str, ...]:
        return tuple(self._maps)

    def get(self, map_id: str) -> WorldMap:
        try:
            return self._maps[map_id]
        except KeyError:
            raise KeyError(f"No map with id '{map_id}'") from None


@dataclass(frozen=True)
class StepResult:
    """What happened when the player tried to take a step."""
    moved: bool
    warped: bool = False
    previous: Optional[Location] = None
    blocked_lines: Tuple[str, ...] = ()   # why a gated warp stopped the player


class Explorer:
    """The player's presence in the world: where they stand and which way they face."""

    def __init__(self, world: World, location: Location, facing: Direction = Direction.DOWN,
                 flags=None):
        self._world = world
        self._location = location
        self._facing = facing
        self._flags = flags  # StoryFlags, used for gated warps
        world.get(location.map_id)  # fail fast on a bad map id

    @property
    def world(self) -> World:
        return self._world

    @property
    def location(self) -> Location:
        return self._location

    @property
    def facing(self) -> Direction:
        return self._facing

    @property
    def current_map(self) -> WorldMap:
        return self._world.get(self._location.map_id)

    def teleport(self, location: Location, facing: Optional[Direction] = None) -> None:
        self._world.get(location.map_id)
        self._location = location
        if facing is not None:
            self._facing = facing

    def face(self, direction: Direction) -> None:
        self._facing = direction

    def step(self, direction: Direction) -> StepResult:
        """Turn to ``direction`` and walk one tile if possible, following any warp."""
        self._facing = direction
        target = self._location.moved(direction)
        if not self.current_map.is_passable(target.x, target.y):
            return StepResult(moved=False)
        previous = self._location
        warp = self.current_map.warp_at(target.x, target.y)
        if warp and warp.required_flag and not (self._flags and self._flags.has(warp.required_flag)):
            return StepResult(moved=False, blocked_lines=warp.blocked_lines or ("You can't go that way yet.",))
        if warp:
            self._location = warp.target
            self._facing = warp.facing
            return StepResult(moved=True, warped=True, previous=previous)
        self._location = target
        return StepResult(moved=True, previous=previous)

    def facing_target(self) -> Optional[Interactable]:
        """The entity in front of the player, looking across counters."""
        m = self.current_map
        ahead = self._location.moved(self._facing)
        if not m.in_bounds(ahead.x, ahead.y):
            return None
        entity = m.entity_at(ahead.x, ahead.y)
        if entity is None and m.tile_at(ahead.x, ahead.y).talk_through:
            beyond = ahead.moved(self._facing)
            if m.in_bounds(beyond.x, beyond.y):
                entity = m.entity_at(beyond.x, beyond.y)
        return entity

    def interact(self, state) -> Optional[Interaction]:
        """Talk to / read whatever is in front of the player (polymorphic ``interact()``)."""
        target = self.facing_target()
        return target.interact(state, self._facing) if target else None

    def roll_encounter(self, rng: Optional[random.Random] = None) -> Optional[str]:
        """After a step: the encounter-table key if a wild creature appears, else None."""
        m = self.current_map
        loc = self._location
        if not m.encounter_table or not m.tile_at(loc.x, loc.y).encounters:
            return None
        roll = (rng or random).random()
        return m.encounter_table if roll < m.encounter_rate else None
