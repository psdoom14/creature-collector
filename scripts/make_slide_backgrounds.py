"""Slide backgrounds drawn by the game's own renderer: 240x135 game pixels, scaled 8x."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.getcwd())
import pygame

from src.model.direction import Direction
from src.ui.components import draw_gba_panel
from src.ui.engine import GameEngine
from src.ui.world_renderer import TILE, CharacterSprites, MapRenderer

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "presentation", "backgrounds")
W, H, SCALE = 240, 135, 8

eng = GameEngine()                       # sets up pygame and the world
world = eng.world


def scene(map_id, cam_x, cam_y, player=None, people=True):
    """A view of ``map_id`` with its people; the camera's top-left is in map pixels."""
    m = world.get(map_id)
    r = MapRenderer(m)
    cam = (cam_x, cam_y)
    s = pygame.Surface((W, H))
    r.draw_ground(s, cam, 0)
    shown = sorted(m.entities, key=lambda e: e.y) if people else [e for e in m.entities if not hasattr(e, "name")]
    for e in shown:
        r.draw_entity(s, e, cam)
    if player:
        (px, py), facing = player
        sprite = CharacterSprites.get("player", facing)
        s.blit(sprite, (px * TILE - cam[0], py * TILE - cam[1] - (sprite.get_height() - TILE)))
    return s


def advance_arrow(s, x, y):
    """The red 'press A' triangle from the game's text box."""
    tri = [(x, y), (x + 8, y), (x + 4, y + 5)]
    pygame.draw.polygon(s, (208, 48, 48), tri)
    pygame.draw.polygon(s, (80, 20, 20), tri, 1)


def save(s, name):
    big = pygame.transform.scale(s, (W * SCALE, H * SCALE))   # nearest neighbour: square pixels
    pygame.image.save(big, os.path.join(OUT, name))
    print("wrote", name)


# --- title: Brookhaven City, the player outside the shop, an empty text box for the title
title = scene("brookhaven_city", 2 * TILE, 2 * TILE, player=((10, 6), Direction.UP))
box = pygame.Rect(4, 92, 232, 39)
draw_gba_panel(title, box)
advance_arrow(title, box.right - 14, box.bottom - 11)
save(title, "bg_title.png")

# --- content: a strip of Route 1 tall grass, the location sign for the slide title,
#     and the game's text panel for the content
content = scene("route_1", 8, 22, people=False)
draw_gba_panel(content, pygame.Rect(4, 4, 150, 18))     # location sign: slide title
draw_gba_panel(content, pygame.Rect(4, 28, 232, 103))   # content panel
advance_arrow(content, 222, 121)
save(content, "bg_content.png")
