"""Link battles end to end: protocol, sessions, real sockets and both battle screens."""
import os
import random
import tempfile
import time
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.data_loader import DataLoader
from src.model.battle import BattleState
from src.model.events import BattleEvent, EventType
from src.model.link_battle import LinkAction, build_link_team
from src.net.connection import Connection, LinkJoiner, LinkListener, MemoryConnection
from src.net.protocol import IdMap, decode_events, encode_events
from src.net.session import GuestLobby, HostLobby, LinkRejected, LinkSession
from src.ui import components
from src.ui.engine import GameEngine
from src.ui.link_scene import LinkBattleScene, LinkMenuScene
from src.ui.overworld_scene import OverworldScene


def connect(loader, host_team=(4, 1), guest_team=(7, 25)):
    a, b = MemoryConnection.pair()
    guest_lobby = GuestLobby(b, "SAM", list(guest_team), loader)
    host = HostLobby(a, "ALEX", list(host_team), loader).poll()
    guest = guest_lobby.poll()
    return host, guest


def auto_play(session: LinkSession):
    if session.finished or session.waiting:
        return
    if session.must_switch:
        party = session.view.player.party
        session.submit(LinkAction.switch(next(i for i, c in enumerate(party.creatures) if not c.is_fainted)))
    else:
        session.submit(LinkAction.move(0))


class TestProtocol(unittest.TestCase):
    def test_ids_and_perspective_flip(self):
        loader = DataLoader()
        team_a, team_b = build_link_team(loader, [4]).creatures, build_link_team(loader, [7]).creatures
        guest_a, guest_b = build_link_team(loader, [4]).creatures, build_link_team(loader, [7]).creatures
        event = BattleEvent(EventType.CREATURE_SENT, "ALEX sent out Charmander!", {"uid": team_a[0].uid})
        wire = encode_events([event], IdMap(team_a, team_b))
        self.assertEqual(wire[0]["data"]["uid"], "A0")
        decoded = decode_events(wire, IdMap(guest_a, guest_b), flip=True)[0]
        self.assertEqual(decoded.event_type, EventType.OPPONENT_SENT, "the host's own creature is the guest's opponent")
        self.assertEqual(decoded.data["uid"], guest_a[0].uid)


class TestSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()

    def setUp(self):
        random.seed(21)

    def test_full_battle_both_games_agree(self):
        host, guest = connect(self.loader)
        for _ in range(200):
            if host.finished and guest.finished:
                break
            auto_play(host)
            auto_play(guest)
            host.poll()
            guest.poll()
        self.assertTrue(host.finished and guest.finished)
        self.assertNotEqual(host.view.state, guest.view.state, "one wins, the other loses")
        self.assertIn(host.view.state, (BattleState.WON, BattleState.LOST))
        host_hp = sorted((c.species_id, c.current_hp) for side in "AB" for c in host.view.trainer(side).party)
        guest_hp = sorted((c.species_id, c.current_hp) for c in list(guest.view.player.party) + list(guest.view._host.party))
        self.assertEqual(host_hp, guest_hp, "both screens show the same HP for every creature")

    def test_host_waits_for_the_guest(self):
        host, guest = connect(self.loader)
        host.submit(LinkAction.move(0))
        self.assertEqual(host.poll(), [])
        self.assertTrue(host.waiting)
        guest.submit(LinkAction.move(0))
        self.assertTrue(host.poll())
        self.assertTrue(guest.poll())

    def test_guest_leaving_is_reported(self):
        host, guest = connect(self.loader)
        guest.close()
        host.poll()
        self.assertIn("left", host.error or "")

    def test_different_versions_are_refused(self):
        a, b = MemoryConnection.pair()
        guest_lobby = GuestLobby(b, "SAM", [7], self.loader)
        host_lobby = HostLobby(a, "ALEX", [4], self.loader)
        host_lobby.fingerprint = "something-else"
        with self.assertRaises(LinkRejected):
            host_lobby.poll()
        with self.assertRaises(LinkRejected):
            guest_lobby.poll()

    def test_empty_team_is_refused(self):
        a, _ = MemoryConnection.pair()
        with self.assertRaises(LinkRejected):
            HostLobby(a, "ALEX", [], self.loader)


class TestRealSockets(unittest.TestCase):
    def test_handshake_and_a_turn_over_tcp(self):
        loader = DataLoader()
        listener = LinkListener(port=0, host="127.0.0.1")
        joiner = LinkJoiner("127.0.0.1", listener.port)
        host_conn = guest_conn = None
        deadline = time.time() + 5
        while (host_conn is None or guest_conn is None) and time.time() < deadline:
            host_conn = host_conn or listener.poll()
            guest_conn = guest_conn or joiner.poll()
            time.sleep(0.01)
        self.assertIsInstance(host_conn, Connection)
        guest_lobby = GuestLobby(guest_conn, "SAM", [7], loader)
        host_lobby = HostLobby(host_conn, "ALEX", [4], loader)
        host = guest = None
        while (host is None or guest is None) and time.time() < deadline:
            host = host or host_lobby.poll()
            guest = guest or guest_lobby.poll()
            time.sleep(0.01)
        self.assertIsNotNone(host)
        self.assertIsNotNone(guest)
        host.submit(LinkAction.move(0))
        guest.submit(LinkAction.move(0))
        got = []
        while not got and time.time() < deadline:
            host.poll()
            got = guest.poll()
            time.sleep(0.01)
        self.assertTrue(any(e.event_type is EventType.MOVE_USED for e in got))
        host.close()
        guest.close()
        listener.close()


class TestLinkScreens(unittest.TestCase):
    def setUp(self):
        pygame.init()
        random.seed(5)
        self.tmp = tempfile.TemporaryDirectory()
        self.engines = [GameEngine(save_path=Path(self.tmp.name) / f"s{i}.json") for i in range(2)]
        for e in self.engines:
            e.push_scene(OverworldScene(e))
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def test_both_players_battle_to_the_end_with_key_presses(self):
        host, guest = connect(self.engines[0].data_loader)
        scenes = [LinkBattleScene(self.engines[0], host), LinkBattleScene(self.engines[1], guest)]
        for engine, scene in zip(self.engines, scenes):
            engine.push_scene(scene)
        for _ in range(1500):
            for engine, scene in zip(self.engines, scenes):
                if engine.current_scene is not scene:
                    continue
                scene.update(0.25)
                scene.draw(engine.native_surface)
                if scene.is_animating:
                    continue
                if scene.sub_state == "ACTION_SELECT":
                    scene.action_menu.selected_index = 0
                    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
                    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
                elif scene.sub_state == "PARTY_SELECT":
                    party = scene.session.view.player.party
                    scene.party_menu.selected_index = next(i for i, c in enumerate(party.creatures) if not c.is_fainted)
                    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
                elif scene.sub_state != "WAITING":
                    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
            if all(isinstance(e.current_scene, OverworldScene) for e in self.engines):
                break
        self.assertTrue(all(isinstance(e.current_scene, OverworldScene) for e in self.engines),
                        "both players return to the overworld")
        self.assertEqual(components.overflow_log(), [])
        # the players' own creatures were not touched by the link battle
        self.assertEqual(self.engines[0].game_state.trainer.party.creatures[0].level, 5)

    def test_link_menu_screens_render(self):
        engine = self.engines[0]
        menu = LinkMenuScene(engine, port=0)
        engine.push_scene(menu)
        for mode in ("MENU", "ENTER_ADDRESS", "CONNECTING", "ERROR"):
            menu.mode = mode
            menu.address = "192.168.100.200"
            menu.message = "Your friend's game is a different version."
            menu.update(0.1)
            menu.draw(engine.native_surface)
        menu.mode = "MENU"
        menu.menu.selected_index = 0
        menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
        self.assertEqual(menu.mode, "HOSTING")
        menu.draw(engine.native_surface)
        menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x))
        self.assertEqual(menu.mode, "MENU")
        self.assertEqual(components.overflow_log(), [])


if __name__ == "__main__":
    unittest.main()
