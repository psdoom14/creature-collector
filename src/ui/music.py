"""Background music: one looping track at a time, chosen by the screen on top.

Each Scene names its track in a ``MUSIC`` class attribute ("menu", "world",
"battle"), or leaves it as None to keep whatever is already playing (so the world
music carries on under the bag or party menus). The engine asks the player to play
the track of the topmost screen that names one.

The sound device is passed in (dependency inversion). The real one is
``pygame.mixer.music``; tests pass a fake. If pygame was built without sound, or
there is no audio device, the player stays silent instead of crashing the game.
"""
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "music"
TRACKS: Dict[str, str] = {
    "menu": "menu.wav",
    "world": "world.mp3",
    "battle": "battle.mp3",
}
FADE_MS = 400
VOLUME = 0.5


def _pygame_music():
    """The real sound device, or None if this pygame has no working mixer."""
    try:
        import pygame
        import pygame.mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return pygame.mixer.music
    except (ImportError, NotImplementedError, Exception) as e:  # no mixer module, or no audio device
        logger.info("Music disabled: %s", e)
        return None


class MusicPlayer:
    """Plays one looping track; switching tracks fades the old one out."""

    def __init__(self, device=None, music_dir: Path = MUSIC_DIR, enabled: bool = True):
        self._device = device if device is not None else (_pygame_music() if enabled else None)
        self._dir = Path(music_dir)
        self._current: Optional[str] = None
        self._muted = False
        if self._device is not None:
            try:
                self._device.set_volume(VOLUME)
            except Exception as e:
                logger.info("Music disabled: %s", e)
                self._device = None

    @property
    def available(self) -> bool:
        return self._device is not None

    @property
    def current(self) -> Optional[str]:
        """The track that should be playing (even when muted or silent)."""
        return self._current

    @property
    def muted(self) -> bool:
        return self._muted

    def play(self, track: Optional[str]) -> None:
        """Loop ``track`` forever. Asking for the track already playing does nothing."""
        if track is None or track == self._current:
            return
        self._current = track
        if self._device is None or self._muted:
            return
        self._start(track)

    def _start(self, track: str) -> None:
        name = TRACKS.get(track)
        path = self._dir / name if name else None
        if path is None or not path.exists():
            logger.warning("No music file for track %r", track)
            return
        try:
            self._device.fadeout(FADE_MS)
            self._device.load(str(path))
            self._device.play(loops=-1, fade_ms=FADE_MS)
        except Exception as e:  # a broken file must never stop the game
            logger.warning("Could not play %s: %s", path.name, e)

    def toggle_mute(self) -> bool:
        """Turn the music off or back on. Returns True if it is now muted."""
        self._muted = not self._muted
        if self._device is not None:
            if self._muted:
                self._device.stop()
            elif self._current:
                self._start(self._current)
        return self._muted

    def stop(self) -> None:
        self._current = None
        if self._device is not None:
            self._device.stop()
