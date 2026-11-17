"""GameState: everything that goes into a save file."""
from typing import Any, Dict, Optional

from src.model.bag import Bag
from src.model.badges import BadgeCase
from src.model.direction import Direction
from src.model.creature import CreatureFactory
from src.model.item import ItemFactory
from src.model.move import MoveFactory
from src.model.pokedex import Pokedex
from src.model.story import StoryFlags
from src.model.trainer import Party, PCBox, Trainer
from src.model.world import Location


class GameState:
    """A snapshot of the player's progress: trainer, Pokédex, location, time and badges."""

    def __init__(
        self,
        trainer: Trainer,
        pokedex: Optional[Pokedex] = None,
        current_route: str = "Route 1",
        play_time: float = 0.0,
        badges=0,
        location: Optional[Location] = None,
        facing: Direction = Direction.DOWN,
        respawn_location: Optional[Location] = None,
        flags: Optional[StoryFlags] = None,
        rival_starter: Optional[int] = None,
    ):
        self.trainer = trainer
        self.pokedex = pokedex or Pokedex()
        self.current_route = current_route
        self._play_time = max(0.0, play_time)
        # ``badges`` may be a count (older saves/tests) or a list of badge names.
        if isinstance(badges, int):
            badges = [f"BADGE {i + 1}" for i in range(badges)]
        self.badge_case = BadgeCase(badges)
        #: Where the player stands (None = the world's start location).
        self.location: Optional[Location] = location
        self.facing: Direction = facing
        #: Where the player wakes up after blacking out (the last healing center used).
        self.respawn_location: Optional[Location] = respawn_location
        #: Story events that have happened ("has_starter", ...).
        self.flags: StoryFlags = flags or StoryFlags()
        #: Species the rival chose (None until the player picks a starter).
        self.rival_starter: Optional[int] = rival_starter

    @property
    def badges(self) -> int:
        """Number of badges earned."""
        return self.badge_case.count

    @property
    def play_time(self) -> float:
        """Seconds played."""
        return self._play_time

    def add_play_time(self, seconds: float) -> None:
        self._play_time += max(0.0, seconds)

    @property
    def play_time_text(self) -> str:
        """Play time as H:MM."""
        minutes = int(self._play_time // 60)
        return f"{minutes // 60}:{minutes % 60:02d}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trainer": self.trainer.to_dict(),
            "pokedex": self.pokedex.to_dict(),
            "current_route": self.current_route,
            "play_time": self._play_time,
            "badges": self.badge_case.to_list(),
            "location": self.location.to_dict() if self.location else None,
            "facing": self.facing.key,
            "respawn_location": self.respawn_location.to_dict() if self.respawn_location else None,
            "flags": self.flags.to_list(),
            "rival_starter": self.rival_starter,
        }

    @staticmethod
    def _creature_from_dict(c_dict: Dict[str, Any], data_loader: Any):
        species_data = data_loader.get_species_data(c_dict["species_id"])
        if not species_data:
            return None
        return CreatureFactory.create(
            species_data=species_data,
            level=c_dict.get("level", 5),
            xp=c_dict.get("xp"),
            moves=[MoveFactory.from_json(m) for m in c_dict.get("moves", [])],
            current_hp=c_dict.get("current_hp"),
            status_effect=c_dict.get("status_effect"),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], data_loader: Any) -> "GameState":
        """Rebuild a GameState from a save dictionary."""
        t = data.get("trainer", {})

        def load_all(dicts):
            return [c for c in (cls._creature_from_dict(d, data_loader) for d in dicts) if c]

        bag = Bag([ItemFactory.from_json(d, quantity=d.get("quantity", 1))
                   for d in t.get("inventory", [])])
        trainer = Trainer(
            name=t.get("name", "Player"),
            party=Party(load_all(t.get("party", []))),
            bag=bag,
            money=t.get("money", 1000),
            pc=PCBox(load_all(t.get("pc", []))),
        )
        return cls(
            trainer=trainer,
            pokedex=Pokedex.from_dict(data.get("pokedex", {})),
            current_route=data.get("current_route", "Route 1"),
            play_time=data.get("play_time", 0.0),
            badges=data.get("badges", 0),
            location=Location.from_dict(data["location"]) if data.get("location") else None,
            facing=Direction.from_name(data.get("facing", "down")),
            respawn_location=(Location.from_dict(data["respawn_location"])
                              if data.get("respawn_location") else None),
            flags=StoryFlags.from_list(data.get("flags", ["has_starter"])),
            rival_starter=data.get("rival_starter"),
        )
