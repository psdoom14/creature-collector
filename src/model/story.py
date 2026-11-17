"""Story progress: flags for things that have happened, and the starter/rival rules."""
from typing import TYPE_CHECKING, Dict, Iterable, List, Sequence

from src.model.creature import Creature
from src.model.type_chart import TypeChart

if TYPE_CHECKING:
    from src.model.game_state import GameState

HAS_STARTER = "has_starter"


def starter_taken_flag(species_id: int) -> str:
    return f"starter_taken_{species_id}"


class StoryFlags:
    """A set of named events that have happened ("has_starter", "got_balls", ...)."""

    def __init__(self, flags: Iterable[str] = ()):
        self._flags = set(flags)

    def has(self, flag: str) -> bool:
        return flag in self._flags

    def set(self, flag: str) -> None:
        self._flags.add(flag)

    def to_list(self) -> List[str]:
        return sorted(self._flags)

    @classmethod
    def from_list(cls, flags: Iterable[str]) -> "StoryFlags":
        return cls(flags)

    def __len__(self) -> int:
        return len(self._flags)


def pick_rival_starter(player_species: int, starters: Dict[int, Sequence[str]],
                       type_chart: TypeChart) -> int:
    """The rival takes the starter whose type hits the player's starter hardest."""
    player_types = list(starters[player_species])
    options = [sid for sid in starters if sid != player_species]

    def advantage(sid: int) -> float:
        return type_chart.get_effectiveness(starters[sid][0], player_types)

    return max(options, key=lambda sid: (advantage(sid), -sid))


def give_starter(state: "GameState", creature: Creature, rival_species: int) -> None:
    """The player takes ``creature``; the rival takes ``rival_species``."""
    state.trainer.receive_creature(creature)
    state.pokedex.register_caught(creature.species_id)
    state.flags.set(HAS_STARTER)
    state.flags.set(starter_taken_flag(creature.species_id))
    state.flags.set(starter_taken_flag(rival_species))
    state.rival_starter = rival_species
