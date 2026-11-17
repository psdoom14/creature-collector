"""Loads JSON data files and instantiates model objects."""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import random

from src.model.type_chart import TypeChart
from src.model.move import Move, MoveFactory
from src.model.creature import Creature, CreatureFactory
from src.model.item import Item, ItemFactory
from src.model.direction import Direction
from src.model.world import Location, World, WorldMap
from src.model.errors import UnknownIdError


class DataLoader:
    """Central repository and factory for game assets and game data."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        if data_dir is None:
            # Default to ../data relative to this file
            self.data_dir = Path(__file__).resolve().parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self._raw_types: Dict[str, Dict[str, float]] = {}
        self._raw_moves: Dict[str, Dict[str, Any]] = {}
        self._raw_creatures_by_id: Dict[int, Dict[str, Any]] = {}
        self._raw_creatures_by_name: Dict[str, Dict[str, Any]] = {}
        self._raw_items: Dict[str, Dict[str, Any]] = {}
        self._raw_encounters: Dict[str, List[Dict[str, Any]]] = {}

        self.load_all()

    def load_all(self) -> None:
        """Load and cache all JSON data files."""
        # 1. Type Chart
        type_file = self.data_dir / "type_chart.json"
        if type_file.exists():
            with open(type_file, "r", encoding="utf-8") as f:
                self._raw_types = json.load(f)

        # 2. Moves
        moves_file = self.data_dir / "moves.json"
        if moves_file.exists():
            with open(moves_file, "r", encoding="utf-8") as f:
                moves_list = json.load(f)
                self._raw_moves = {m["id"]: m for m in moves_list}

        # 3. Creatures
        creatures_file = self.data_dir / "creatures.json"
        if creatures_file.exists():
            with open(creatures_file, "r", encoding="utf-8") as f:
                creatures_list = json.load(f)
                for c in creatures_list:
                    self._raw_creatures_by_id[c["id"]] = c
                    self._raw_creatures_by_name[c["name"].lower()] = c

        # 4. Items
        items_file = self.data_dir / "items.json"
        if items_file.exists():
            with open(items_file, "r", encoding="utf-8") as f:
                items_list = json.load(f)
                self._raw_items = {i["id"]: i for i in items_list}

        # 5. Encounters
        enc_file = self.data_dir / "encounters.json"
        if enc_file.exists():
            with open(enc_file, "r", encoding="utf-8") as f:
                routes = json.load(f)
                for r in routes:
                    self._raw_encounters[r["route_name"]] = r.get("encounters", [])

    # --- world -----------------------------------------------------------
    def load_world(self) -> World:
        """Build the World from every data/maps/*.json file."""
        maps = []
        for path in sorted((self.data_dir / "maps").glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                maps.append(WorldMap.from_dict(json.load(f)))
        return World(maps)

    def _world_info(self) -> Dict[str, Any]:
        with open(self.data_dir / "world.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def start_location(self) -> Location:
        """Where a new game begins."""
        return Location.from_dict(self._world_info()["start"])

    def start_facing(self) -> Direction:
        return Direction.from_name(self._world_info()["start"].get("facing", "down"))

    def get_type_chart(self) -> TypeChart:
        """Create and return a TypeChart instance."""
        return TypeChart(self._raw_types)

    def get_move(self, move_id: str) -> Move:
        """Instantiate a Move object from move_id."""
        if move_id not in self._raw_moves:
            raise UnknownIdError("move", move_id, "moves.json")
        return MoveFactory.from_json(self._raw_moves[move_id])

    def get_species_data(self, species_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve raw species data dictionary."""
        return self._raw_creatures_by_id.get(species_id)

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Return every item entry from items.json (for the debug menu)."""
        return list(self._raw_items.values())

    def get_all_species(self) -> List[Dict[str, Any]]:
        """Return list of all species entries."""
        return list(self._raw_creatures_by_id.values())

    def get_creature(self, identifier: Union[int, str], level: int = 5) -> Creature:
        """
        Instantiate a creature by ID or Name, automatically assigning appropriate
        moves up to its current level.
        """
        if isinstance(identifier, int):
            data = self._raw_creatures_by_id.get(identifier)
        else:
            data = self._raw_creatures_by_name.get(str(identifier).lower())

        if not data:
            raise UnknownIdError("creature", identifier, "creatures.json")

        # Determine moves learned up to this level (take last 4)
        learned_move_ids: List[str] = []
        for entry in data.get("learnable_moves", []):
            if entry["level"] <= level:
                learned_move_ids.append(entry["move_id"])

        active_move_ids = learned_move_ids[-4:] if len(learned_move_ids) >= 4 else learned_move_ids
        # If no moves learned, default to tackle
        if not active_move_ids and "tackle" in self._raw_moves:
            active_move_ids = ["tackle"]

        moves = [self.get_move(mid) for mid in active_move_ids if mid in self._raw_moves]

        return CreatureFactory.create(
            species_data=data,
            level=level,
            moves=moves,
        )

    def get_item(self, item_id: str, quantity: int = 1) -> Item:
        """Instantiate an Item object with given quantity."""
        if item_id not in self._raw_items:
            raise UnknownIdError("item", item_id, "items.json")
        return ItemFactory.from_json(self._raw_items[item_id], quantity=quantity)

    def get_wild_encounter(self, route_name: str) -> Optional[Creature]:
        """Generate a random wild creature encounter based on route encounter tables."""
        table = self._raw_encounters.get(route_name)
        if not table:
            return None

        # Weighted selection
        weights = [entry.get("weight", 10) for entry in table]
        chosen = random.choices(table, weights=weights, k=1)[0]

        species_id = chosen["creature_id"]
        lvl_min, lvl_max = chosen.get("level_range", [3, 5])
        level = random.randint(lvl_min, lvl_max)

        return self.get_creature(species_id, level=level)
