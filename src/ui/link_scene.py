"""Link battle screens: the host/join menu and the two-player battle screen.

``LinkBattleScene`` is a ``BattleScene`` subclass: it keeps all of the drawing,
animations and event playback, and overrides only what changes when the opponent
is a person: choices go to a ``LinkSession`` and results arrive later.
"""
from typing import List, Optional

import pygame

from src.model.events import BattleEvent
from src.model.link_battle import LINK_LEVEL, LinkAction
from src.net.connection import DEFAULT_PORT, ConnectionLost, LinkJoiner, LinkListener, local_ip_addresses
from src.net.session import GuestLobby, HostLobby, LinkRejected, LinkSession
from src.ui.battle_scene import BattleScene
from src.ui.components import (
    MenuBox, draw_crisp_text, draw_fitted_text, draw_gba_panel, get_font, small_font, wrap_text,
)
from src.ui.scene import Scene

CONFIRM = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z)
BACK = (pygame.K_ESCAPE, pygame.K_x)
MAX_ADDRESS = 15


class LinkMenuScene(Scene):
    """Modes: MENU, HOSTING, ENTER_ADDRESS, CONNECTING, ERROR."""

    def __init__(self, engine, port: int = DEFAULT_PORT):
        super().__init__(engine)
        self.font = get_font(10)
        self.font_sm = small_font()
        self.port = port
        self.mode = "MENU"
        self.menu = MenuBox(pygame.Rect(8, 26, 100, 52), ["HOST", "JOIN", "BACK"])
        self.address = ""
        self.message = ""
        self.listener: Optional[LinkListener] = None
        self.joiner: Optional[LinkJoiner] = None
        self.lobby = None
        self.timer = 0.0
        self._addresses = ["127.0.0.1"]

    # ------------------------------------------------------------------
    def _team(self) -> List[int]:
        return [c.species_id for c in self.engine.game_state.trainer.party]

    def _fail(self, message: str) -> None:
        self._cleanup()
        self.mode = "ERROR"
        self.message = message

    def _cleanup(self) -> None:
        if self.listener:
            self.listener.close()
            self.listener = None
        self.joiner = None
        if self.lobby:
            self.lobby.conn.close()
            self.lobby = None

    def _start_battle(self, session: LinkSession) -> None:
        if self.listener:
            self.listener.close()
            self.listener = None
        self.lobby = None
        self.engine.pop_scene()
        self.engine.push_scene(LinkBattleScene(self.engine, session))

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if self.mode == "MENU":
            if key in BACK:
                self.engine.pop_scene()
                return
            choice = self.menu.handle_input(key)
            if choice == 0:
                self._host()
            elif choice == 1:
                self.mode, self.address = "ENTER_ADDRESS", ""
            elif choice == 2:
                self.engine.pop_scene()
        elif self.mode == "ENTER_ADDRESS":
            if key in (pygame.K_ESCAPE,):
                self.mode = "MENU"
            elif key == pygame.K_BACKSPACE:
                self.address = self.address[:-1]
            elif key == pygame.K_RETURN and self.address:
                self.joiner = LinkJoiner(self.address, self.port)
                self.mode = "CONNECTING"
            else:
                ch = getattr(event, "unicode", "") or ""
                if len(ch) == 1 and (ch.isdigit() or ch == ".") and len(self.address) < MAX_ADDRESS:
                    self.address += ch
        elif self.mode in ("HOSTING", "CONNECTING"):
            if key in BACK:
                self._cleanup()
                self.mode = "MENU"
        elif self.mode == "ERROR" and key in CONFIRM + BACK:
            self.mode = "MENU"

    def _host(self) -> None:
        if not self._team():
            self._fail("You need at least one creature to battle.")
            return
        try:
            self.listener = LinkListener(self.port)
        except OSError as e:
            self._fail(f"Can't host on port {self.port}: {e.strerror or e}")
            return
        self._addresses = local_ip_addresses()   # looked up once, not every frame
        self.mode = "HOSTING"

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.timer += dt
        try:
            if self.mode == "HOSTING":
                if self.lobby is None and self.listener:
                    conn = self.listener.poll()
                    if conn:
                        self.lobby = HostLobby(conn, self.engine.game_state.trainer.name, self._team(),
                                               self.engine.data_loader)
                if self.lobby:
                    session = self.lobby.poll()
                    if session:
                        self._start_battle(session)
            elif self.mode == "CONNECTING":
                if self.lobby is None and self.joiner:
                    conn = self.joiner.poll()
                    if conn:
                        self.lobby = GuestLobby(conn, self.engine.game_state.trainer.name, self._team(),
                                                self.engine.data_loader)
                if self.lobby:
                    session = self.lobby.poll()
                    if session:
                        self._start_battle(session)
        except (ConnectionLost, LinkRejected) as e:
            self._fail(str(e))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((40, 64, 104))
        draw_gba_panel(surface, pygame.Rect(4, 2, 232, 18))
        draw_fitted_text(surface, "LINK BATTLE", 12, 3, 140, self.font)
        draw_fitted_text(surface, f"ALL LV{LINK_LEVEL}", 152, 6, 76, self.font_sm, align="right")

        info = pygame.Rect(4, 84, 232, 72)
        lines: List[str] = []
        if self.mode == "MENU":
            self.menu.draw(surface)
            panel = pygame.Rect(112, 26, 124, 52)
            draw_gba_panel(surface, panel)
            team = self.engine.game_state.trainer.party
            draw_fitted_text(surface, "YOUR TEAM", panel.x + 6, panel.y + 4, 112, self.font_sm)
            names = ", ".join(c.name for c in team) or "(none)"
            for i, line in enumerate(wrap_text(names, 112, self.font_sm)[:2]):
                draw_fitted_text(surface, line, panel.x + 6, panel.y + 18 + i * 12, 112, self.font_sm)
            lines = ["Both players must be on the same Wi-Fi.",
                     "HOST: wait for your friend to join.",
                     "JOIN: type the host's address."]
        elif self.mode == "HOSTING":
            info = pygame.Rect(4, 26, 232, 130)   # addresses + the firewall tip need room
            dots = "." * (1 + int(self.timer * 2) % 3)
            addresses = self._addresses
            lines = [f"Your address: {addresses[0]}"] + [f"      or: {a}" for a in addresses[1:3]]
            lines += [f"Port {self.port}. Waiting for a friend{dots}",
                      "Friend can't join? This laptop's firewall",
                      "may block it: allow the port, or swap",
                      "so the other laptop hosts.  X: cancel"]
        elif self.mode == "ENTER_ADDRESS":
            cursor = "_" if int(self.timer * 2) % 2 == 0 else ""
            box = pygame.Rect(4, 26, 232, 52)
            draw_gba_panel(surface, box)
            draw_fitted_text(surface, "HOST'S ADDRESS", box.x + 8, box.y + 4, 216, self.font_sm)
            draw_crisp_text(surface, self.address + cursor, box.x + 8, box.y + 20, self.font)
            lines = ["Type the host's address,", "then press Enter.", "Esc: back"]
        elif self.mode == "CONNECTING":
            lines = [f"Connecting to {self.address}...", "X: cancel"]
        elif self.mode == "ERROR":
            info = pygame.Rect(4, 26, 232, 130)   # the error gets the whole screen
            lines = wrap_text(self.message, 216, self.font_sm)[:7] + ["", "Press Z to go back."]

        draw_gba_panel(surface, info)
        for i, line in enumerate(lines[:9]):
            draw_fitted_text(surface, line, info.x + 8, info.y + 5 + i * 13, 216, self.font_sm)


class LinkBattleScene(BattleScene):
    """A battle against another person. Inherits everything about drawing and playback."""

    def __init__(self, engine, session: LinkSession):
        self.session = session
        super().__init__(engine, session.view.opponent, battle=session.view)

    # --- sending choices -----------------------------------------------------
    def _submit(self, action: LinkAction) -> None:
        self.session.submit(action)
        self._show_waiting()
        self._pull()

    def _show_waiting(self) -> None:
        self.sub_state = "WAITING"
        self.textbox.set_message(f"Waiting for {self.session.opponent_name}...")
        self.textbox.advance()

    def _input_action_select(self, key: int) -> None:
        choice = self.action_menu.handle_input(key)
        if choice == 1:
            self.textbox.set_message("Items can't be used in link battles.")
            self.sub_state = "DIALOGUE"
        elif choice == 3:
            self._submit(LinkAction.forfeit())
        elif choice is not None:
            # FIGHT and POKÉMON open the same menus as a normal battle
            self.action_menu.selected_index = choice
            super()._input_action_select(pygame.K_RETURN)

    def _input_move_select(self, key: int) -> None:
        if key in BACK:
            self.sub_state = "ACTION_SELECT"
            return
        choice = self.move_menu.handle_input(key)
        if choice is not None:
            self._submit(LinkAction.move(choice))

    def _input_party_select(self, key: int) -> None:
        if key in BACK and not self.party_menu_forced:
            self.sub_state = "ACTION_SELECT"
            return
        choice = self.party_menu.handle_input(key)
        if choice is None:
            return
        party = self.session.view.player.party
        chosen = party.creatures[choice]
        if chosen.is_fainted or chosen is self.session.view.player_creature:
            self.textbox.set_message(f"{chosen.name} can't be sent out!")
            self.textbox.advance()
            return
        self._submit(LinkAction.switch(choice))

    def _input_waiting(self, key: int) -> None:
        pass  # nothing to press while the other player decides

    # --- receiving results ------------------------------------------------------
    def _pull(self) -> None:
        events: List[BattleEvent] = self.session.poll()
        if events:
            if self.sub_state == "WAITING":
                self._queue(events)
            else:
                self.queued_events.extend(events)
        if self.session.error and self.sub_state != "END":
            self.queued_events.clear()
            self.sub_state = "END"
            self.textbox.set_message(self.session.error)

    def update(self, dt: float) -> None:
        super().update(dt)
        self._pull()

    def _choose_next_state(self) -> None:
        if self.session.finished or self.session.error:
            self.sub_state = "END"
            self.textbox.set_message("The link battle is over. Press Enter.")
        elif self.session.must_switch:
            self._open_party_menu(forced=True)
        elif self.session.waiting:
            self._show_waiting()
        else:
            self.sub_state = "ACTION_SELECT"

    def _input_end(self, key: int) -> None:
        if key not in CONFIRM:
            return
        self.session.close()
        self.engine.pop_scene()   # back to the overworld; the link teams were copies
