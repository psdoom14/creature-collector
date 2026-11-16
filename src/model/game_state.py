"""Game state representation combining Trainer, Party, Inventory, Pokédex, and Progression."""
from typing import Dict, Any, Optional
from src.model.trainer import Trainer, Party
from src.model.pokedex import Pokedex
from src.model.creature import CreatureFactory
from src.model.move import MoveFactory
from src.model.item import ItemFactory


class GameState:
    """Represents the complete snapshot of a player's save game."""

    def __init__(
        self,
        trainer: Trainer,
        pokedex: Optional[Pokedex] = None,
        current_route: str = "Route 1",
        play_time: float = 0.0,
        badges: int = 0,
    ):
        self.trainer = trainer
        self.pokedex = pokedex or Pokedex()
        self.current_route = current_route
        self.play_time = play_time
        self.badges = badges

    def to_dict(self) -> Dict[str, Any]:
        """Convert game state to a JSON-serializable dictionary."""
        return {
            "trainer": self.trainer.to_dict(),
            "pokedex": self.pokedex.to_dict(),
            "current_route": self.current_route,
            "play_time": self.play_time,
            "badges": self.badges,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], data_loader: Any) -> "GameState":
        """Reconstruct full GameState object from serialized dictionary."""
        trainer_data = data.get("trainer", {})
        trainer_name = trainer_data.get("name", "Red")
        money = trainer_data.get("money", 1000)

        # Reconstruct party creatures
        party_creatures = []
        for c_dict in trainer_data.get("party", []):
            species_data = data_loader.get_species_data(c_dict["species_id"])
            if not species_data:
                continue

            moves = [MoveFactory.from_json(m) for m in c_dict.get("moves", [])]
            creature = CreatureFactory.create(
                species_data=species_data,
                level=c_dict.get("level", 5),
                xp=c_dict.get("xp"),
                moves=moves,
                current_hp=c_dict.get("current_hp"),
                status_effect=c_dict.get("status_effect"),
            )
            party_creatures.append(creature)

        party = Party(party_creatures)

        # Reconstruct inventory items
        inventory = {}
        for item_dict in trainer_data.get("inventory", []):
            item = ItemFactory.from_json(item_dict, quantity=item_dict.get("quantity", 1))
            inventory[item.id] = item

        trainer = Trainer(
            name=trainer_name,
            party=party,
            inventory=inventory,
            money=money,
        )

        pokedex = Pokedex.from_dict(data.get("pokedex", {}))

        return cls(
            trainer=trainer,
            pokedex=pokedex,
            current_route=data.get("current_route", "Route 1"),
            play_time=data.get("play_time", 0.0),
            badges=data.get("badges", 0),
        )
