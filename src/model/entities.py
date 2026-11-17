"""Things on a map the player can talk to or inspect.

    Interactable (abstract)          has a position, blocks movement, interact()
    ├── Sign                         shows its text
    ├── StarterBall                  offers its creature until it has been taken
    ├── ItemBall                     an item lying on the ground: picked up once, then gone
    └── Character (abstract)         has a name and a facing direction
        └── NPC                      turns to face you and talks
            ├── Healer               talks, then heals your whole party
            ├── Professor            different lines before/after you have a starter, gives a gift once
            ├── GiftGiver            gives you items once, then says something else
            ├── Shopkeeper           opens the shop screen (buy and sell)
            └── TrainerNPC           spots you in its line of sight and battles (TrainerBattle)
                ├── RivalTrainer     team built around the starter the rival picked
                └── GymLeader        battles with a smart AI and awards a badge (GymBattle)

``interact(state, player_facing)`` gets the whole GameState (trainer, flags, ...),
so each subclass decides what it needs. The overworld just calls it.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple, Type

from src.model.direction import Direction
from src.model.errors import GameDataError

if TYPE_CHECKING:
    from src.model.battle import TrainerBattle
    from src.model.creature import Creature
    from src.model.game_state import GameState
    from src.model.type_chart import TypeChart
    from src.model.world import Location, WorldMap


@dataclass(frozen=True)
class Interaction:
    """The result of interacting with something: who speaks, what they say, and any side effect."""
    speaker: str
    lines: Tuple[str, ...]
    effect: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class Interactable(ABC):
    """Abstract base for anything on a map the player can face and press A on."""

    KIND: str = ""
    _registry: Dict[str, Type["Interactable"]] = {}

    def __init__(self, x: int, y: int):
        self._x = x
        self._y = y

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.KIND:
            Interactable._registry[cls.KIND] = cls

    @property
    def position(self) -> Tuple[int, int]:
        return self._x, self._y

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def blocks_movement(self) -> bool:
        return True

    def is_gone(self, flags) -> bool:
        """Whether this has left the map for good (a picked-up item ball), judged from story flags."""
        return False

    def is_present(self, state: "GameState") -> bool:
        """Whether this is drawn on the map and blocks the way."""
        return not self.is_gone(state.flags)

    def notices(self, state: "GameState", world_map: "WorldMap", player: "Location") -> bool:
        """Whether this reacts to the player just by being seen (trainers do)."""
        return False

    @abstractmethod
    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        """React to the player, who is facing ``player_facing`` towards this object."""

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "Interactable":
        """Factory: build the subclass registered under ``data["kind"]``."""
        kind = data.get("kind", "")
        sub = cls._registry.get(kind)
        if sub is None:
            raise GameDataError(f"Unknown entity kind '{kind}'")
        return sub._from_data(data)

    @classmethod
    @abstractmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Interactable":
        """Build an instance of this subclass from map data."""


class Sign(Interactable):
    """A signpost: shows its text when read."""
    KIND = "sign"

    def __init__(self, x: int, y: int, lines: Sequence[str]):
        super().__init__(x, y)
        self._lines = tuple(lines)

    @property
    def lines(self) -> Tuple[str, ...]:
        return self._lines

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        return Interaction("", self._lines)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Sign":
        return cls(data["x"], data["y"], data.get("lines", []))


class StarterBall(Interactable):
    """A ball on the professor's table holding one of the starter creatures."""
    KIND = "starter_ball"

    def __init__(self, x: int, y: int, species_id: int):
        super().__init__(x, y)
        self._species_id = species_id

    @property
    def species_id(self) -> int:
        return self._species_id

    def _taken_flag(self) -> str:
        return f"starter_taken_{self._species_id}"

    def is_gone(self, flags) -> bool:
        return flags.has(self._taken_flag())

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        if not self.is_present(state):
            return Interaction("", ("The table is empty here.",))
        if state.flags.has("has_starter"):
            return Interaction("", ("You already have a partner.",))
        return Interaction("", (), effect="offer_starter", data={"species_id": self._species_id})

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "StarterBall":
        return cls(data["x"], data["y"], int(data["species"]))


class ItemBall(Interactable):
    """An item lying on the ground. Picking it up sets a flag, so it stays gone after saving."""
    KIND = "item_ball"

    def __init__(self, x: int, y: int, ball_id: str, item_id: str, quantity: int = 1):
        super().__init__(x, y)
        self._ball_id = ball_id
        self._item_id = item_id
        self._quantity = max(1, quantity)

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def picked_flag(self) -> str:
        return f"picked_{self._ball_id}"

    def is_gone(self, flags) -> bool:
        return flags.has(self.picked_flag)

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        if self.is_gone(state.flags):
            return Interaction("", ("There's nothing here.",))
        state.flags.set(self.picked_flag)
        return Interaction("", (f"{state.trainer.name} found something!",), effect="give_items",
                           data={"items": {self._item_id: self._quantity}})

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "ItemBall":
        return cls(data["x"], data["y"], data["id"], data["item"], int(data.get("quantity", 1)))


class Character(Interactable, ABC):
    """A person on the map: has a name, faces a direction, and is drawn with a colour palette."""

    def __init__(self, x: int, y: int, name: str, facing: Direction = Direction.DOWN,
                 palette: str = "green"):
        super().__init__(x, y)
        self._name = name
        self._facing = facing
        self._palette = palette

    @property
    def name(self) -> str:
        return self._name

    @property
    def facing(self) -> Direction:
        return self._facing

    @property
    def palette(self) -> str:
        return self._palette

    def turn_to(self, player_facing: Direction) -> None:
        """Turn to look at a player who is facing ``player_facing``."""
        self._facing = player_facing.opposite


class NPC(Character):
    """A townsperson who turns to face you and says their lines."""
    KIND = "npc"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str],
                 facing: Direction = Direction.DOWN, palette: str = "green"):
        super().__init__(x, y, name, facing, palette)
        self._lines = tuple(lines)

    @property
    def lines(self) -> Tuple[str, ...]:
        return self._lines

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        return Interaction(self._name, self._lines)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "NPC":
        return cls(data["x"], data["y"], data.get("name", "???"), data.get("lines", []),
                   Direction.from_name(data.get("facing", "down")), data.get("palette", "green"))


class Healer(NPC):
    """The healing-center nurse: greets you, heals the whole party, says goodbye."""
    KIND = "healer"

    FAREWELL = ("Your creatures are fully rested.", "Come back any time!")

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str],
                 facing: Direction = Direction.DOWN, palette: str = "pink",
                 farewell: Sequence[str] = ()):
        super().__init__(x, y, name, lines, facing, palette)
        self._farewell = tuple(farewell) or self.FAREWELL

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        greeting = super().interact(state, player_facing)
        state.trainer.party.heal_all()
        return Interaction(self._name, greeting.lines + self._farewell, effect="healed")

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Healer":
        return cls(data["x"], data["y"], data.get("name", "NURSE"), data.get("lines", []),
                   Direction.from_name(data.get("facing", "down")), data.get("palette", "pink"),
                   data.get("farewell", []))


class Professor(NPC):
    """The professor: one speech before you have a starter, another after, and a one-time gift."""
    KIND = "professor"
    GIFT_FLAG = "got_professor_gift"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str],
                 after_lines: Sequence[str] = (), gift: Optional[Dict[str, int]] = None,
                 gift_lines: Sequence[str] = (), facing: Direction = Direction.DOWN,
                 palette: str = "brown"):
        super().__init__(x, y, name, lines, facing, palette)
        self._after_lines = tuple(after_lines) or self._lines
        self._gift = dict(gift or {})
        self._gift_lines = tuple(gift_lines) or ("Take these. They'll help you on your journey!",)

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        if not state.flags.has("has_starter"):
            return Interaction(self._name, self._lines)
        if self._gift and not state.flags.has(self.GIFT_FLAG):
            state.flags.set(self.GIFT_FLAG)
            return Interaction(self._name, self._gift_lines, effect="give_items",
                               data={"items": dict(self._gift)})
        return Interaction(self._name, self._after_lines)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Professor":
        return cls(data["x"], data["y"], data.get("name", "PROFESSOR"), data.get("lines", []),
                   data.get("after_lines", []), data.get("gift"), data.get("gift_lines", []),
                   Direction.from_name(data.get("facing", "down")), data.get("palette", "brown"))


class GiftGiver(NPC):
    """Someone who hands you items the first time you talk, then just chats."""
    KIND = "gift_npc"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str], gift_id: str,
                 gift: Dict[str, int], after_lines: Sequence[str] = (),
                 facing: Direction = Direction.DOWN, palette: str = "green"):
        super().__init__(x, y, name, lines, facing, palette)
        self._gift_flag = f"gift_{gift_id}"
        self._gift = dict(gift)
        self._after_lines = tuple(after_lines) or self._lines

    @property
    def gift_flag(self) -> str:
        return self._gift_flag

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        if state.flags.has(self._gift_flag):
            return Interaction(self._name, self._after_lines)
        state.flags.set(self._gift_flag)
        return Interaction(self._name, self._lines, effect="give_items", data={"items": dict(self._gift)})

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "GiftGiver":
        return cls(data["x"], data["y"], data.get("name", "???"), data.get("lines", []),
                   data["id"], data.get("gift", {}), data.get("after_lines", []),
                   Direction.from_name(data.get("facing", "down")), data.get("palette", "green"))


class Shopkeeper(NPC):
    """The shop clerk: greets you, then the shop screen opens with this clerk's stock."""
    KIND = "shopkeeper"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str], stock: Sequence[str],
                 facing: Direction = Direction.DOWN, palette: str = "blue"):
        super().__init__(x, y, name, lines, facing, palette)
        self._stock = tuple(stock)

    @property
    def stock(self) -> Tuple[str, ...]:
        return self._stock

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        return Interaction(self._name, self._lines or ("Welcome! How may I help you?",),
                           effect="open_shop", data={"stock": self._stock})

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "Shopkeeper":
        return cls(data["x"], data["y"], data.get("name", "CLERK"), data.get("lines", []),
                   data.get("stock", []), Direction.from_name(data.get("facing", "down")),
                   data.get("palette", "blue"))


CreatureFactory = Callable[[int, int], "Creature"]


class TrainerNPC(NPC):
    """A trainer who challenges you when you walk into their line of sight (or talk to them)."""
    KIND = "trainer"

    def __init__(self, x: int, y: int, name: str, lines: Sequence[str], trainer_id: str,
                 title: str = "TRAINER", party: Sequence[Sequence[int]] = (), prize: int = 0,
                 sight: int = 3, defeat_lines: Sequence[str] = (), after_lines: Sequence[str] = (),
                 facing: Direction = Direction.DOWN, palette: str = "blue"):
        super().__init__(x, y, name, lines, facing, palette)
        self._trainer_id = trainer_id
        self._title = title
        self._party = [tuple(entry) for entry in party]
        self._prize = prize
        self._sight = sight
        self._defeat_lines = tuple(defeat_lines) or ("You're strong!",)
        self._after_lines = tuple(after_lines) or self._defeat_lines

    # --- data ------------------------------------------------------------
    @property
    def trainer_id(self) -> str:
        return self._trainer_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def sight(self) -> int:
        return self._sight

    @property
    def defeat_flag(self) -> str:
        return f"defeated_{self._trainer_id}"

    def is_defeated(self, state: "GameState") -> bool:
        return state.flags.has(self.defeat_flag)

    # --- behaviour ---------------------------------------------------------
    def notices(self, state: "GameState", world_map: "WorldMap", player: "Location") -> bool:
        """True if the player stands within ``sight`` tiles straight ahead, with nothing in between."""
        if self._sight <= 0 or self.is_defeated(state):
            return False
        x, y = self._x, self._y
        for _ in range(self._sight):
            x, y = x + self._facing.dx, y + self._facing.dy
            if (x, y) == (player.x, player.y):
                return True
            if not world_map.in_bounds(x, y) or not world_map.is_passable(x, y):
                return False
        return False

    def interact(self, state: "GameState", player_facing: Direction) -> Interaction:
        self.turn_to(player_facing)
        if self.is_defeated(state):
            return Interaction(self._name, self._after_lines)
        return self.challenge()

    def challenge(self) -> Interaction:
        """The pre-battle speech, with an instruction to start the battle afterwards."""
        return Interaction(self._name, self._lines, effect="start_battle", data={"trainer": self})

    def _party_spec(self, state: "GameState") -> List[Tuple[int, int]]:
        """(species id, level) for each creature this trainer uses."""
        return list(self._party)

    def _make_ai(self, type_chart: "TypeChart"):
        from src.model.battle_ai import RandomAI
        return RandomAI()

    def _battle_class(self):
        from src.model.battle import TrainerBattle
        return TrainerBattle

    def _battle_kwargs(self, state: "GameState") -> Dict[str, Any]:
        """Extra arguments for the battle class (GymLeader adds the badge)."""
        return {}

    def build_battle(self, state: "GameState", type_chart: "TypeChart",
                     creature_factory: CreatureFactory, move_source=None) -> "TrainerBattle":
        """Factory method: each trainer subclass builds the right kind of battle."""
        party = [creature_factory(species, level) for species, level in self._party_spec(state)]
        battle_cls = self._battle_class()
        return battle_cls(
            state.trainer, party, type_chart,
            trainer_name=self._name, trainer_title=self._title, prize=self._prize,
            defeat_lines=self._defeat_lines, flags=state.flags, defeat_flag=self.defeat_flag,
            ai=self._make_ai(type_chart), move_source=move_source,
            **self._battle_kwargs(state),
        )

    @classmethod
    def _kwargs_from_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            x=data["x"], y=data["y"], name=data.get("name", "TRAINER"), lines=data.get("lines", []),
            trainer_id=data["id"], title=data.get("title", "TRAINER"), party=data.get("party", []),
            prize=data.get("prize", 0), sight=data.get("sight", 3),
            defeat_lines=data.get("defeat_lines", []), after_lines=data.get("after_lines", []),
            facing=Direction.from_name(data.get("facing", "down")), palette=data.get("palette", "blue"),
        )

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "TrainerNPC":
        return cls(**cls._kwargs_from_data(data))


class RivalTrainer(TrainerNPC):
    """The rival: leads with the starter they took in the lab."""
    KIND = "rival"

    def __init__(self, *args, starter_level: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self._starter_level = starter_level

    def _party_spec(self, state: "GameState") -> List[Tuple[int, int]]:
        lead = state.rival_starter or 1
        return [(lead, self._starter_level)] + super()._party_spec(state)

    def _make_ai(self, type_chart: "TypeChart"):
        from src.model.battle_ai import SmartAI
        return SmartAI(type_chart, randomness=0.5)

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "RivalTrainer":
        kwargs = cls._kwargs_from_data(data)
        kwargs.setdefault("palette", "purple")
        return cls(starter_level=data.get("starter_level", 5), **kwargs)


class GymLeader(TrainerNPC):
    """A gym leader: talk to them to battle; winning earns their badge."""
    KIND = "gym_leader"

    def __init__(self, *args, badge: str = "BADGE", **kwargs):
        kwargs.setdefault("sight", 0)
        super().__init__(*args, **kwargs)
        self._badge = badge

    @property
    def badge(self) -> str:
        return self._badge

    def _make_ai(self, type_chart: "TypeChart"):
        from src.model.battle_ai import SmartAI
        return SmartAI(type_chart)

    def _battle_class(self):
        from src.model.battle import GymBattle
        return GymBattle

    def _battle_kwargs(self, state: "GameState") -> Dict[str, Any]:
        return {"badge": self._badge, "badge_case": state.badge_case}

    @classmethod
    def _from_data(cls, data: Dict[str, Any]) -> "GymLeader":
        kwargs = cls._kwargs_from_data(data)
        kwargs["sight"] = data.get("sight", 0)
        return cls(badge=data.get("badge", "BADGE"), **kwargs)
