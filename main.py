"""Main entry point for the Pokémon-style Creature Collector game."""
import sys
import os

# Set standard locale if not set to prevent xkb Compose warnings
if "en_IN" in os.environ.get("LC_ALL", "") or "en_IN" in os.environ.get("LANG", ""):
    os.environ["LC_ALL"] = "C.UTF-8"

from src.ui.engine import GameEngine
from src.ui.title_scene import TitleScene


def main():
    # If running in environment without DISPLAY or headless test
    if "--terminal" in sys.argv or "--cli" in sys.argv:
        from terminal_demo import main as run_terminal
        run_terminal()
        return

    # Only Linux signals a desktop through DISPLAY / WAYLAND_DISPLAY; Windows and macOS
    # always have one, so the check must not run there.
    if sys.platform.startswith("linux") and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("\nNo graphical display detected in environment.")
        print("Launching terminal prototype instead (or pass --cli)...")
        from terminal_demo import main as run_terminal
        run_terminal()
        return

    engine = GameEngine(title="Pokémon - Creature Collector (GBA)")
    engine.push_scene(TitleScene(engine))
    engine.run()


if __name__ == "__main__":
    main()
