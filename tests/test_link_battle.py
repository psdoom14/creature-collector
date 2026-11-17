"""Link battles: the two-player battle rules (model only, no network)."""
import random
import unittest

from src.data_loader import DataLoader
from src.model.battle import Battle, BattleState
from src.model.events import EventType
from src.model.link_battle import LINK_LEVEL, SIDE_A, SIDE_B, LinkAction, LinkBattle, build_link_team
from src.model.trainer import Trainer


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()

    def setUp(self):
        random.seed(11)

    def battle(self, team_a=(4,), team_b=(7,)):
        a = Trainer("ALEX", build_link_team(self.loader, team_a))
        b = Trainer("SAM", build_link_team(self.loader, team_b))
        return LinkBattle(a, b, self.chart)

    def fight(self, battle, limit=200):
        for _ in range(limit):
            if not battle.is_active:
                return
            needed = battle.expected_sides()
            actions = {}
            for side in needed:
                if side in battle.needs_switch:
                    party = battle.trainer(side).party
                    idx = next(i for i, c in enumerate(party.creatures) if not c.is_fainted)
                    actions[side] = LinkAction.switch(idx)
                else:
                    actions[side] = LinkAction.move(0)
            battle.resolve(actions)
        self.fail("battle did not end")


class TestTeams(_Base):
    def test_every_creature_is_the_link_level_with_full_hp(self):
        team = build_link_team(self.loader, [4, 19, 25])
        self.assertEqual([c.level for c in team], [LINK_LEVEL] * 3)
        self.assertTrue(all(c.current_hp == c.max_hp for c in team))

    def test_both_machines_build_identical_teams(self):
        t1 = build_link_team(self.loader, [6, 9])
        t2 = build_link_team(DataLoader(), [6, 9])
        for a, b in zip(t1, t2):
            self.assertEqual((a.species_id, a.level, a.max_hp, a.attack, [m.id for m in a.moves]),
                             (b.species_id, b.level, b.max_hp, b.attack, [m.id for m in b.moves]))

    def test_team_is_capped_at_six(self):
        self.assertEqual(len(build_link_team(self.loader, list(range(1, 11)))), 6)


class TestLinkBattle(_Base):
    def test_is_a_battle_without_running_or_catching(self):
        b = self.battle()
        self.assertIsInstance(b, Battle)
        self.assertFalse(b.can_flee)
        self.assertFalse(b.can_catch)

    def test_a_turn_needs_both_players(self):
        b = self.battle()
        self.assertEqual(b.expected_sides(), {SIDE_A, SIDE_B})
        with self.assertRaises(ValueError):
            b.resolve({SIDE_A: LinkAction.move(0)})

    def test_both_creatures_act_in_a_turn(self):
        b = self.battle((4,), (7,))
        events = b.resolve({SIDE_A: LinkAction.move(0), SIDE_B: LinkAction.move(0)})
        users = [e.data.get("user") for e in events if e.event_type is EventType.MOVE_USED]
        self.assertEqual(sorted(users), ["Charmander", "Squirtle"])

    def test_switch_happens_before_moves(self):
        b = self.battle((4,), (7, 1))
        events = b.resolve({SIDE_A: LinkAction.move(0), SIDE_B: LinkAction.switch(1)})
        kinds = [e.event_type for e in events]
        self.assertLess(kinds.index(EventType.OPPONENT_SENT), kinds.index(EventType.MOVE_USED))
        self.assertEqual(b.opponent.species_id, 1)

    def test_faint_asks_only_that_player_for_a_replacement(self):
        b = self.battle((6,), (19, 16))          # Charizard vs Rattata + Pidgey, all Lv50
        for _ in range(10):
            if b.needs_switch:
                break
            b.resolve({SIDE_A: LinkAction.move(0), SIDE_B: LinkAction.move(0)})
        self.assertEqual(b.needs_switch, {SIDE_B})
        self.assertEqual(b.expected_sides(), {SIDE_B})
        events = b.resolve({SIDE_B: LinkAction.switch(1)})
        self.assertEqual(events[0].event_type, EventType.OPPONENT_SENT)
        self.assertEqual(b.needs_switch, set())

    def test_battle_ends_with_a_winner_and_no_xp(self):
        b = self.battle((6,), (19,))
        xp_before = b.trainer(SIDE_A).party.creatures[0].xp
        self.fight(b)
        self.assertIn(b.state, (BattleState.WON, BattleState.LOST))
        self.assertIn(b.winner, (SIDE_A, SIDE_B))
        self.assertEqual(b.trainer(SIDE_A).party.creatures[0].xp, xp_before, "no XP in link battles")

    def test_forfeit(self):
        b = self.battle()
        events = b.resolve({SIDE_A: LinkAction.move(0), SIDE_B: LinkAction.forfeit()})
        self.assertEqual(b.winner, SIDE_A)
        self.assertEqual(b.state, BattleState.WON)
        self.assertIn(EventType.BATTLE_WON, [e.event_type for e in events])

    def test_actions_round_trip_as_dicts(self):
        for action in (LinkAction.move(2), LinkAction.switch(3), LinkAction.forfeit()):
            self.assertEqual(LinkAction.from_dict(action.to_dict()), action)


if __name__ == "__main__":
    unittest.main()
