"""Saving and loading the GameState as JSON, safely.

* Saving writes to a temporary file first and then swaps it in, so a crash or
  a full disk can never leave a half-written save behind.
* Every way a save can fail to load (missing, not JSON, wrong shape, unknown
  ids, newer version) becomes one of the ``SaveError`` subclasses, with the
  original error kept as ``__cause__``.
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from src.data_loader import DataLoader
from src.model.errors import CorruptSaveError, GameError, SaveNotFoundError, SaveWriteError
from src.model.game_state import GameState

logger = logging.getLogger(__name__)
PathLike = Union[str, Path]


class SaveManager:
    """File persistence for the GameState."""

    #: Bumped whenever the save format changes incompatibly.
    SAVE_VERSION = 1

    @classmethod
    def save_game(cls, game_state: GameState, filepath: PathLike = "savegame.json") -> bool:
        """Write ``game_state`` to ``filepath``. Returns True, or raises ``SaveWriteError``."""
        path = Path(filepath)
        data = {"version": cls.SAVE_VERSION, **game_state.to_dict()}
        tmp_name: Optional[str] = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".save-", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_name, path)       # atomic: the old save is replaced only on success
            tmp_name = None
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error("Could not save the game to %s: %s", path, e)
            raise SaveWriteError(f"Could not save the game: {e}") from e
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.remove(tmp_name)

    @classmethod
    def load_game(cls, filepath: PathLike = "savegame.json",
                  data_loader: Optional[DataLoader] = None) -> GameState:
        """Read a save file back into a GameState, or raise a ``SaveError`` subclass."""
        path = Path(filepath)
        if not path.is_file():
            raise SaveNotFoundError(f"No save file at {path}")
        loader = data_loader or DataLoader()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CorruptSaveError(f"The save file is not valid JSON (line {e.lineno})") from e
        except (OSError, UnicodeDecodeError) as e:
            raise CorruptSaveError(f"The save file could not be read: {e}") from e

        if not isinstance(data, dict):
            raise CorruptSaveError("The save file does not contain a saved game")
        version = data.get("version", 1)
        if not isinstance(version, int) or version > cls.SAVE_VERSION:
            raise CorruptSaveError(f"The save file is from a newer version of the game ({version})")

        try:
            return GameState.from_dict(data, loader)
        except (GameError, KeyError, TypeError, ValueError, AttributeError) as e:
            raise CorruptSaveError(f"The save file is damaged: {e}") from e

    @staticmethod
    def has_save(filepath: PathLike = "savegame.json") -> bool:
        """Whether a save file exists (it may still turn out to be damaged)."""
        return Path(filepath).is_file()
