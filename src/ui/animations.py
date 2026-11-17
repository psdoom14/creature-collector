"""GBA-style battle animations.

    Animation (abstract)              a timed effect: update(dt), modify(side, mods), draw(surface, layout)
    ├── SlideIn, SendOut, HitBlink, FaintDrop, ScreenShake      sprite motion
    ├── BallThrow, BallWobble                                   catching
    ├── LevelUpGlow, StatusSparkle, StatArrows, HealSparkle     feedback
    └── MoveAnimation (abstract)      one subclass per move type, chosen by MoveAnimation.create()
        ├── ImpactAnimation           Normal / Fighting / anything unknown
        ├── ProjectileAnimation (abstract): particles fly from attacker to target
        │   ├── EmberAnimation (Fire, Dragon)   ├── WaterAnimation (Water)
        │   ├── LeafAnimation (Grass)           ├── IceAnimation (Ice)
        │   └── ShadowAnimation (Poison, Ghost)
        ├── ThunderAnimation (Electric) ├── PsychicAnimation (Psychic)
        ├── QuakeAnimation (Ground, Rock) ├── GustAnimation (Flying)
        └── StatusMoveAnimation       any status move

The battle scene keeps a list of running animations. Each frame it asks every
animation to ``modify`` the two sprites (offset, visibility, scale, white flash)
and then to ``draw`` its own overlay. It never checks which kind it holds.
"""
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Type

import pygame

FOE = "foe"
PLAYER = "player"

WHITE = (248, 248, 248)
STATUS_TINTS = {
    "burn": (240, 96, 48), "poison": (168, 72, 184), "paralyze": (240, 208, 48), "sleep": (152, 160, 176),
}


@dataclass
class SpriteMods:
    """How animations change a creature sprite this frame."""
    dx: float = 0.0
    dy: float = 0.0
    visible: bool = True
    scale: float = 1.0
    white: float = 0.0     # 0 = normal colours, 1 = a white silhouette
    sink: bool = False     # clip the sprite at its platform (it drops "into the ground")


@dataclass(frozen=True)
class BattleLayout:
    """Where things are on the 240x160 battle screen."""
    foe_center: Tuple[int, int] = (181, 46)
    player_center: Tuple[int, int] = (58, 90)
    foe_size: int = 52
    player_size: int = 56

    def center(self, side: str) -> Tuple[int, int]:
        return self.foe_center if side == FOE else self.player_center

    def other(self, side: str) -> str:
        return PLAYER if side == FOE else FOE


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


# ----------------------------------------------------------------------
# Base class
# ----------------------------------------------------------------------
class Animation(ABC):
    """A timed visual effect. Subclasses override ``modify`` and/or ``draw``."""

    duration: float = 0.5
    #: While a blocking animation runs, the battle screen ignores the confirm key.
    blocking: bool = True

    def __init__(self, side: Optional[str] = None):
        self.side = side
        self.t = 0.0

    @property
    def progress(self) -> float:
        return min(1.0, self.t / self.duration) if self.duration > 0 else 1.0

    @property
    def done(self) -> bool:
        return self.t >= self.duration

    def update(self, dt: float) -> None:
        self.t += dt

    def modify(self, side: str, mods: SpriteMods) -> None:
        """Change how the sprite on ``side`` is drawn this frame (default: no change)."""

    @abstractmethod
    def draw(self, surface: pygame.Surface, layout: BattleLayout) -> None:
        """Draw this animation's own overlay (particles, a ball...)."""


# ----------------------------------------------------------------------
# Sprite motion
# ----------------------------------------------------------------------
class SlideIn(Animation):
    """The wild creature slides in from the edge at the start of a battle."""
    duration = 0.7
    hides_hud = True   # the info cards appear once it has arrived

    def modify(self, side, mods):
        if side == self.side:
            start = -200 if side == FOE else 200
            mods.dx += _lerp(start, 0, _ease_out(self.progress))

    def draw(self, surface, layout):
        pass


class SendOut(Animation):
    """A creature pops out of its ball: a white silhouette that grows, then gets its colours."""
    duration = 0.55

    def modify(self, side, mods):
        if side == self.side:
            p = self.progress
            mods.scale *= _lerp(0.1, 1.0, _ease_out(min(1.0, p / 0.7)))
            mods.white = max(mods.white, 1.0 - max(0.0, (p - 0.6) / 0.4))

    def draw(self, surface, layout):
        if self.progress < 0.35:  # the burst of light from the ball
            cx, cy = layout.center(self.side)
            r = int(4 + 22 * self.progress / 0.35)
            for i in range(8):
                a = i * math.pi / 4
                pygame.draw.line(surface, WHITE, (cx, cy), (cx + math.cos(a) * r, cy + math.sin(a) * r), 2)


class HitBlink(Animation):
    """The target flickers when hit (stronger hits flicker longer)."""

    def __init__(self, side, strong: bool = False):
        super().__init__(side)
        self.duration = 0.6 if strong else 0.4

    def modify(self, side, mods):
        if side == self.side and not self.done:
            mods.visible = mods.visible and int(self.t * 16) % 2 == 1

    def draw(self, surface, layout):
        pass


class FaintDrop(Animation):
    """A fainted creature slides down out of sight behind its platform."""
    duration = 0.6
    persist = True   # stays down until a new creature is sent out

    def modify(self, side, mods):
        if side == self.side:
            mods.dy += 60 * self.progress ** 2
            mods.sink = True

    def draw(self, surface, layout):
        pass


class ScreenShake(Animation):
    """A short shake of both sprites, for super-effective hits and earthquakes."""
    duration = 0.35

    def modify(self, side, mods):
        if not self.done:
            mods.dx += math.sin(self.t * 70) * 3 * (1 - self.progress)

    def draw(self, surface, layout):
        pass


# ----------------------------------------------------------------------
# Catching
# ----------------------------------------------------------------------
def _draw_ball(surface, x, y, r=6, open_amount=0.0):
    x, y = int(x), int(y)
    pygame.draw.circle(surface, WHITE, (x, y), r)
    top = pygame.Rect(x - r, y - r - int(open_amount * 4), r * 2 + 1, r)
    pygame.draw.rect(surface, (224, 56, 48), top)
    pygame.draw.circle(surface, (40, 40, 48), (x, y), r, 1)
    pygame.draw.line(surface, (40, 40, 48), (x - r, y), (x + r, y))
    pygame.draw.circle(surface, WHITE, (x, y), 2)


class BallThrow(Animation):
    """The ball flies in an arc to the wild creature, opens, and swallows it in a flash."""
    duration = 0.9
    start = (40, 120)
    persist = True     # the creature stays inside until the wobble result
    holds_foe = True

    def __init__(self):
        super().__init__(FOE)

    def modify(self, side, mods):
        if side == FOE and self.progress > 0.6:
            q = (self.progress - 0.6) / 0.4
            mods.white = max(mods.white, 1.0)
            mods.scale *= 1 - q
            if q >= 1:
                mods.visible = False

    def draw(self, surface, layout):
        tx, ty = layout.foe_center
        p = min(1.0, self.progress / 0.6)
        x = _lerp(self.start[0], tx, p)
        y = _lerp(self.start[1], ty - 10, p) - math.sin(p * math.pi) * 50
        _draw_ball(surface, x, y, open_amount=1.0 if 0.6 < self.progress < 0.9 else 0.0)


class BallWobble(Animation):
    """The ball sits on the ground and wobbles ``shakes`` times; then it clicks shut or bursts open."""

    holds_foe = True

    def __init__(self, shakes: int, caught: bool):
        super().__init__(FOE)
        self.shakes = shakes
        self.caught = caught
        self.persist = caught   # a caught creature stays in the ball
        self.duration = 0.4 + 0.5 * shakes + 0.4

    def modify(self, side, mods):
        if side == FOE:
            if self.caught or self.t < self.duration - 0.4:
                mods.visible = False
            else:  # breaking free: a white flash fading into the creature
                mods.white = max(mods.white, 1 - (self.t - (self.duration - 0.4)) / 0.4)

    def draw(self, surface, layout):
        tx, ty = layout.foe_center
        ground = ty + 10   # resting on the platform
        wobble_end = 0.4 + 0.5 * self.shakes
        tilt = 0.0
        if 0.4 <= self.t < wobble_end:
            local = (self.t - 0.4) % 0.5
            tilt = math.sin(local / 0.5 * math.pi * 2) * 4 if local < 0.3 else 0
        if self.caught or self.t < wobble_end:
            _draw_ball(surface, tx + tilt, ground)
            if self.caught and self.t >= wobble_end:  # "click": little stars
                for i in range(3):
                    sx = tx - 10 + i * 10
                    pygame.draw.line(surface, (248, 216, 64), (sx, ground - 14), (sx, ground - 20), 2)


# ----------------------------------------------------------------------
# Feedback
# ----------------------------------------------------------------------
class _Sparkles(Animation):
    """Shared code: small particles around a creature."""
    duration = 0.8
    colour = WHITE

    def __init__(self, side, seed: int = 0):
        super().__init__(side)
        rng = random.Random(seed)
        self._points = [(rng.uniform(-22, 22), rng.uniform(-22, 22), rng.uniform(0, 0.4)) for _ in range(10)]

    def _point(self, base, ox, oy, delay):
        return base[0] + ox, base[1] + oy

    def draw(self, surface, layout):
        base = layout.center(self.side)
        for ox, oy, delay in self._points:
            local = (self.t - delay) / (self.duration - delay)
            if 0 <= local <= 1:
                x, y = self._point(base, ox, oy, local)
                r = max(1, int(3 * (1 - abs(local - 0.5) * 2)))
                pygame.draw.circle(surface, self.colour, (int(x), int(y)), r)


class LevelUpGlow(_Sparkles):
    """Level up: rising blue-white sparkles and a short glow."""
    colour = (136, 200, 248)

    def _point(self, base, ox, oy, local):
        return base[0] + ox, base[1] + 20 - local * 50

    def modify(self, side, mods):
        if side == self.side:
            mods.white = max(mods.white, 0.5 * math.sin(self.progress * math.pi))


class StatusSparkle(_Sparkles):
    """A status condition lands: particles in the status colour swirl around the target."""

    def __init__(self, side, status: str):
        super().__init__(side, seed=len(status))
        self.colour = STATUS_TINTS.get(status, WHITE)

    def _point(self, base, ox, oy, local):
        a = local * math.pi * 2 + ox
        return base[0] + math.cos(a) * 22, base[1] + math.sin(a) * 14 + oy * 0.3


class HealSparkle(_Sparkles):
    """HP restored: green sparkles drifting up."""
    colour = (120, 216, 120)

    def _point(self, base, ox, oy, local):
        return base[0] + ox, base[1] + oy - local * 20


class StatArrows(Animation):
    """A stat rises or falls: arrows streaming up or down over the creature."""
    duration = 0.8

    def __init__(self, side, rising: bool):
        super().__init__(side)
        self.rising = rising

    def draw(self, surface, layout):
        cx, cy = layout.center(self.side)
        colour = (248, 120, 88) if self.rising else (88, 136, 248)
        for i in range(4):
            phase = (self.progress * 2 + i * 0.25) % 1
            y = cy + (20 - 40 * phase if self.rising else -20 + 40 * phase)
            x = cx - 18 + i * 12
            d = -1 if self.rising else 1
            pygame.draw.polygon(surface, colour, [(x, y + 4 * d), (x - 4, y - 2 * d), (x + 4, y - 2 * d)])


# ----------------------------------------------------------------------
# Move animations
# ----------------------------------------------------------------------
class MoveAnimation(Animation, ABC):
    """An attack's visual. ``create()`` picks the subclass registered for the move's type."""

    TYPES: Tuple[str, ...] = ()
    _registry: Dict[str, Type["MoveAnimation"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for move_type in cls.TYPES:
            MoveAnimation._registry[move_type] = cls

    def __init__(self, attacker: str, move_type: str = "Normal"):
        super().__init__(attacker)
        self.attacker = attacker
        self.move_type = move_type

    @property
    def target(self) -> str:
        return FOE if self.attacker == PLAYER else PLAYER

    @staticmethod
    def create(move_type: str, category: str, attacker: str) -> "MoveAnimation":
        """Factory: a status move sparkles; otherwise the class registered for the type."""
        if category == "status":
            return StatusMoveAnimation(attacker, move_type)
        cls = MoveAnimation._registry.get(move_type, ImpactAnimation)
        return cls(attacker, move_type)


class ImpactAnimation(MoveAnimation):
    """Physical hit: the attacker lunges forward and a star bursts on the target."""
    TYPES = ("Normal", "Fighting", "Bug", "Steel")
    duration = 0.5

    def modify(self, side, mods):
        if side == self.attacker and self.progress < 0.5:
            lunge = math.sin(self.progress / 0.5 * math.pi) * 12
            mods.dx += lunge if self.attacker == PLAYER else -lunge
            mods.dy += -lunge / 2 if self.attacker == PLAYER else lunge / 2

    def draw(self, surface, layout):
        if 0.35 < self.progress < 0.8:
            cx, cy = layout.center(self.target)
            r = int(6 + 10 * (self.progress - 0.35) / 0.45)
            points = []
            for i in range(10):
                a = i * math.pi / 5
                rr = r if i % 2 == 0 else r / 2
                points.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            pygame.draw.polygon(surface, WHITE, points)
            pygame.draw.polygon(surface, (248, 200, 64), points, 1)


class ProjectileAnimation(MoveAnimation, ABC):
    """Shared code: a stream of particles travels from attacker to target, then bursts."""
    duration = 0.8
    count = 6

    @abstractmethod
    def particle(self, surface, x: float, y: float, i: int, local: float) -> None:
        """Draw particle ``i`` at (x, y); ``local`` is its own 0-1 progress."""

    def path(self, a, b, local, i):
        return _lerp(a[0], b[0], local), _lerp(a[1], b[1], local)

    def draw(self, surface, layout):
        a, b = layout.center(self.attacker), layout.center(self.target)
        for i in range(self.count):
            local = (self.progress * 1.6 - i * 0.1)
            if 0 <= local <= 1:
                x, y = self.path(a, b, local, i)
                self.particle(surface, x, y, i, local)


class EmberAnimation(ProjectileAnimation):
    TYPES = ("Fire", "Dragon")

    def particle(self, surface, x, y, i, local):
        colour = (248, 200, 64) if i % 2 else (240, 96, 48)
        if self.move_type == "Dragon":
            colour = (152, 96, 232) if i % 2 else (96, 64, 200)
        pygame.draw.circle(surface, colour, (int(x), int(y)), 4)
        pygame.draw.circle(surface, (248, 240, 160), (int(x), int(y) - 1), 2)


class WaterAnimation(ProjectileAnimation):
    TYPES = ("Water",)

    def path(self, a, b, local, i):
        x, y = super().path(a, b, local, i)
        return x, y + math.sin(local * math.pi * 3 + i) * 5

    def particle(self, surface, x, y, i, local):
        pygame.draw.circle(surface, (104, 160, 248), (int(x), int(y)), 4)
        pygame.draw.circle(surface, (208, 232, 255), (int(x) - 1, int(y) - 1), 1)


class LeafAnimation(ProjectileAnimation):
    TYPES = ("Grass",)

    def path(self, a, b, local, i):
        x, y = super().path(a, b, local, i)
        return x, y - math.sin(local * math.pi) * (10 + i * 3)

    def particle(self, surface, x, y, i, local):
        a = local * 12 + i
        dx, dy = math.cos(a) * 4, math.sin(a) * 2
        pygame.draw.polygon(surface, (88, 176, 72), [(x - dx, y - dy), (x + dy, y - dx), (x + dx, y + dy), (x - dy, y + dx)])


class IceAnimation(ProjectileAnimation):
    TYPES = ("Ice",)

    def particle(self, surface, x, y, i, local):
        pygame.draw.polygon(surface, (168, 224, 240), [(x, y - 5), (x + 3, y), (x, y + 5), (x - 3, y)])


class ShadowAnimation(ProjectileAnimation):
    TYPES = ("Poison", "Ghost")

    def particle(self, surface, x, y, i, local):
        pygame.draw.circle(surface, (136, 72, 160), (int(x), int(y)), 5)
        pygame.draw.circle(surface, (192, 128, 216), (int(x) - 1, int(y) - 1), 2)


class ThunderAnimation(MoveAnimation):
    """Electric: the screen flashes and a jagged bolt strikes the target."""
    TYPES = ("Electric",)
    duration = 0.6

    def draw(self, surface, layout):
        if int(self.t * 20) % 3 == 0 and self.progress < 0.7:
            cx, cy = layout.center(self.target)
            points, x, y = [], cx, 0
            rng = random.Random(int(self.t * 20))
            while y < cy:
                points.append((x, y))
                y += 10
                x = cx + rng.randint(-8, 8)
            points.append((cx, cy))
            pygame.draw.lines(surface, (248, 232, 96), False, points, 3)
            pygame.draw.lines(surface, WHITE, False, points, 1)


class PsychicAnimation(MoveAnimation):
    """Psychic: rings ripple out over the target."""
    TYPES = ("Psychic",)
    duration = 0.8

    def draw(self, surface, layout):
        cx, cy = layout.center(self.target)
        for i in range(3):
            r = int(((self.progress * 2 + i / 3) % 1) * 30)
            if r > 2:
                pygame.draw.circle(surface, (232, 104, 168), (cx, cy), r, 2)


class QuakeAnimation(MoveAnimation):
    """Ground / Rock: the screen shakes and rocks fall on the target."""
    TYPES = ("Ground", "Rock")
    duration = 0.8

    def modify(self, side, mods):
        if not self.done:
            mods.dx += math.sin(self.t * 60) * 3

    def draw(self, surface, layout):
        cx, cy = layout.center(self.target)
        for i in range(4):
            local = self.progress * 1.5 - i * 0.15
            if 0 <= local <= 1:
                x = cx - 18 + i * 12
                y = _lerp(cy - 50, cy, local)
                pygame.draw.circle(surface, (152, 120, 80), (int(x), int(y)), 4)
                pygame.draw.circle(surface, (96, 72, 48), (int(x), int(y)), 4, 1)


class GustAnimation(MoveAnimation):
    """Flying: swirling wind lines around the target."""
    TYPES = ("Flying",)
    duration = 0.8

    def draw(self, surface, layout):
        cx, cy = layout.center(self.target)
        for i in range(3):
            a = self.progress * 10 + i * 2.1
            r = 10 + i * 7
            rect = pygame.Rect(cx - r, cy - r // 2, r * 2, r)
            pygame.draw.arc(surface, (216, 232, 248), rect, a, a + 2.2, 2)


class StatusMoveAnimation(MoveAnimation):
    """A status move: a glimmer on the target (or the user, for self-boosts)."""
    TYPES = ()
    duration = 0.6

    def draw(self, surface, layout):
        cx, cy = layout.center(self.target)
        for i in range(5):
            a = self.progress * 6 + i * 1.256
            x, y = cx + math.cos(a) * 18, cy + math.sin(a) * 12
            pygame.draw.circle(surface, (248, 240, 168), (int(x), int(y)), 2)
