"""Core Pygame engine, scene manager, and display scaler."""
import pygame
import sys
from typing import List, Optional
from pathlib import Path

from src.ui.scene import Scene
from src.data_loader import DataLoader
from src.model.game_state import GameState
from src.model.trainer import Trainer, Party
from src.model.pokedex import Pokedex


class GameEngine:
    """Manages window setup, 240x160 native surface scaling, and scene transitions."""

    NATIVE_WIDTH = 240
    NATIVE_HEIGHT = 160
    SCALE = 3

    def __init__(self, title: str = "Pokémon - Creature Collector"):
        pygame.init()
        pygame.display.set_caption(title)

        self.window_width = self.NATIVE_WIDTH * self.SCALE
        self.window_height = self.NATIVE_HEIGHT * self.SCALE

        self.window_surface = pygame.display.set_mode((self.window_width, self.window_height))
        self.native_surface = pygame.Surface((self.NATIVE_WIDTH, self.NATIVE_HEIGHT))

        self.clock = pygame.time.Clock()
        self.is_running = False

        self.scene_stack: List[Scene] = []
        self.data_loader = DataLoader()
        self.game_state: Optional[GameState] = None

        self._init_default_game_state()

    def _init_default_game_state(self) -> None:
        """Create initial player and inventory state."""
        starter = self.data_loader.get_creature(4, level=5)  # Charmander
        party = Party([starter])
        trainer = Trainer("Red", party, money=1200)

        # Starter kit
        trainer.add_item(self.data_loader.get_item("poke_ball", 10), 10)
        trainer.add_item(self.data_loader.get_item("great_ball", 3), 3)
        trainer.add_item(self.data_loader.get_item("potion", 5), 5)
        trainer.add_item(self.data_loader.get_item("revive", 2), 2)

        pokedex = Pokedex()
        pokedex.register_caught(starter.species_id)

        self.game_state = GameState(trainer, pokedex, current_route="Route 1")

    @property
    def current_scene(self) -> Optional[Scene]:
        return self.scene_stack[-1] if self.scene_stack else None

    def push_scene(self, scene: Scene, **kwargs) -> None:
        if self.current_scene:
            self.current_scene.on_exit()
        self.scene_stack.append(scene)
        scene.on_enter(**kwargs)

    def pop_scene(self) -> Optional[Scene]:
        if self.scene_stack:
            old = self.scene_stack.pop()
            old.on_exit()
            if self.current_scene:
                self.current_scene.on_enter()
            return old
        return None

    def change_scene(self, scene: Scene, **kwargs) -> None:
        while self.scene_stack:
            old = self.scene_stack.pop()
            old.on_exit()
        self.scene_stack.append(scene)
        scene.on_enter(**kwargs)

    def run(self) -> None:
        self.is_running = True
        while self.is_running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                    break
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    # Toggle fullscreen
                    pygame.display.toggle_fullscreen()
                elif self.current_scene:
                    self.current_scene.handle_event(event)

            if not self.is_running:
                break

            if self.current_scene:
                self.current_scene.update(dt)
                self.current_scene.draw(self.native_surface)

            # Scale native surface (240x160) up to window surface (720x480)
            scaled = pygame.transform.scale(self.native_surface, (self.window_width, self.window_height))
            self.window_surface.blit(scaled, (0, 0))
            pygame.display.flip()

        pygame.quit()
