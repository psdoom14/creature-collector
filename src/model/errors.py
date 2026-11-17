"""The game's own exception hierarchy.

    GameError                          base for every error the game raises on purpose
    ├── GameDataError (ValueError)     something in data/*.json is wrong
    │   └── UnknownIdError (KeyError)  an id that isn't in the data (move, item, species, map...)
    ├── RuleViolation (ValueError)     code tried to break a game rule (7 creatures in a party...)
    └── SaveError                      problems with the save file
        ├── SaveNotFoundError (FileNotFoundError)
        ├── CorruptSaveError           the file exists but can't be turned back into a game
        └── SaveWriteError (OSError)   the game couldn't be written to disk

Each one also inherits the matching built-in exception, so code that catches
``ValueError`` / ``KeyError`` / ``OSError`` keeps working, while game code can
catch exactly what it expects (``except SaveError``) instead of ``except Exception``.
"""


class GameError(Exception):
    """Base class for every error the game raises deliberately."""


class GameDataError(GameError, ValueError):
    """A data file (creatures, moves, items, maps...) contains something invalid."""


class UnknownIdError(GameDataError, KeyError):
    """An id was looked up that doesn't exist in the data."""

    def __init__(self, kind: str, identifier, source: str = ""):
        self.kind = kind
        self.identifier = identifier
        where = f" in {source}" if source else ""
        super().__init__(f"Unknown {kind} '{identifier}'{where}")

    def __str__(self) -> str:  # KeyError would otherwise wrap the message in quotes
        return self.args[0]


class RuleViolation(GameError, ValueError):
    """Code tried to do something the game's rules forbid."""


class SaveError(GameError):
    """Base class for save-file problems."""


class SaveNotFoundError(SaveError, FileNotFoundError):
    """There is no save file."""


class CorruptSaveError(SaveError):
    """The save file exists but can't be loaded (not JSON, missing fields, unknown ids...)."""


class SaveWriteError(SaveError, OSError):
    """The game couldn't be written to disk. The previous save, if any, is untouched."""
