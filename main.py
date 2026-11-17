"""Main entry point for the Pokémon-style Creature Collector game."""
import os
import sys

# Set standard locale if not set to prevent xkb Compose warnings
if "en_IN" in os.environ.get("LC_ALL", "") or "en_IN" in os.environ.get("LANG", ""):
    os.environ["LC_ALL"] = "C.UTF-8"

from src.ui.engine import GameEngine
from src.ui.title_scene import TitleScene


def main():
    # Only Linux signals a desktop through DISPLAY / WAYLAND_DISPLAY; Windows and macOS
    # always have one, so the check must not run there.
    if sys.platform.startswith("linux") and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("No graphical display found. Run the game from a desktop session.")
        sys.exit(1)

    engine = GameEngine(title="Pokémon - Creature Collector (GBA)")
    engine.push_scene(TitleScene(engine))
    engine.run()


if __name__ == "__main__":
    main()
