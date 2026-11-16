"""Handles saving and loading game state to/from JSON files."""
import json
from pathlib import Path
from typing import Union
from src.model.game_state import GameState
from src.data_loader import DataLoader


class SaveManager:
    """Provides file IO persistence for the GameState."""

    @staticmethod
    def save_game(game_state: GameState, filepath: Union[str, Path] = "savegame.json") -> bool:
        """Serialize and save the game state to disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(game_state.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving game: {e}")
            return False

    @staticmethod
    def load_game(filepath: Union[str, Path] = "savegame.json", data_loader: DataLoader = None) -> GameState:
        """Load and reconstruct game state from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Save file not found at {path}")

        if data_loader is None:
            data_loader = DataLoader()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return GameState.from_dict(data, data_loader)

    @staticmethod
    def has_save(filepath: Union[str, Path] = "savegame.json") -> bool:
        """Check if save file exists."""
        return Path(filepath).exists()
