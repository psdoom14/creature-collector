"""Base Scene class for the UI scene manager."""
from abc import ABC, abstractmethod
from typing import Optional, Any


class Scene(ABC):
    """Abstract base class for all game screens (Overworld, Battle, Menu, etc.)."""

    #: Background music for this screen ("menu", "world", "battle"), or None to keep
    #: whatever is already playing (pop-up menus keep the world music going).
    MUSIC: Optional[str] = None

    def __init__(self, engine: Any):
        self.engine = engine

    def on_enter(self, **kwargs) -> None:
        """Called when this scene becomes the active scene."""
        pass

    def on_exit(self) -> None:
        """Called when this scene is removed or suspended."""
        pass

    @abstractmethod
    def handle_event(self, event: Any) -> None:
        """Process a single Pygame input event."""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance scene logic by dt seconds."""
        pass

    @abstractmethod
    def draw(self, surface: Any) -> None:
        """Render scene visuals to the native 240x160 surface."""
        pass
