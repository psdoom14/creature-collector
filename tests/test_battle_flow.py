"""Phase 2 battle behaviour: switching, move learning, blackout, evolution readiness, ids.

See docs/PLAN.md bugs B4, B5, B7, B9, B11.
"""
import random
import unittest

from src.data_loader import DataLoader
from src.model.battle import Battle, BattleState, WildBattle
from src.model.battle_ai import BattleAI, RandomAI
from src.model.events import EventType
from src.model.trainer import Party, Trainer


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()

    def setUp(self):
        random.seed(99)

    def wild_battle(self, party, wild, **kwargs):
        kwargs.setdefault("move_source", self.loader.get_move)
        return WildBattle(Trainer("A", Party(party)), wild, self.chart, **kwargs)

    def win_one_turn(self, battle):
        """Keep attacking until the battle ends (healing the player so it can't lose)."""
        for _ in range(20):
            if not battle.is_active:
                return
            battle.player_creature.heal(999)
            battle.execute_move(0)
        self.fail("battle did not end")


class TestBattleHierarchy(_Base):
    def test_battle_is_abstract(self):
        with self.assertRaises(TypeError):
            Battle(Trainer("A"), self.loader.get_creature(19), self.chart)  # type: ignore[abstract]

    def test_wild_battle_allows_running_and_catching(self):
        b = self.wild_battle([self.loader.get_creature(4)], self.loader.get_creature(19))
        self.assertTrue(b.can_flee)
        self.assertTrue(b.can_catch)
        self.assertIn("Wild Rattata", b.intro_message)

    def test_random_ai_is_a_battle_ai(self):
        self.assertTrue(issubclass(RandomAI, BattleAI))
        mon = self.loader.get_creature(19)
        self.assertIn(RandomAI().choose_move(mon, self.loader.get_creature(4)), mon.moves)


class TestSwitching(_Base):
    def test_faint_with_backup_requires_choosing_next_creature(self):
        lead = self.loader.get_creature(19, level=2)
        backup = self.loader.get_creature(4, level=30)
        wild = self.loader.get_creature(6, level=60)
        b = self.wild_battle([lead, backup], wild)

        for _ in range(10):
            if b.state is BattleState.SELECTING_SWITCH:
                break
            b.execute_move(0)

        self.assertEqual(b.state, BattleState.SELECTING_SWITCH)
        self.assertIs(b.player_creature, lead, "fainted lead stays out until the player picks")
        self.assertEqual(b.execute_move(0)[0].event_type, EventType.INVALID_ACTION)

        events = b.switch_creature(1)
        self.assertEqual(events[0].event_type, EventType.CREATURE_SENT)
        self.assertIs(b.player_creature, backup)
        self.assertEqual(b.state, BattleState.SELECTING_ACTION)
        self.assertNotIn(EventType.MOVE_USED, [e.event_type for e in events],
                         "a forced switch doesn't give the opponent a free attack")

    def test_voluntary_switch_costs_a_turn(self):
        lead = self.loader.get_creature(4, level=10)
        backup = self.loader.get_creature(7, level=10)
        b = self.wild_battle([lead, backup], self.loader.get_creature(19, level=5))

        events = b.switch_creature(1)
        kinds = [e.event_type for e in events]
        self.assertEqual(kinds[0], EventType.CREATURE_SENT)
        self.assertIn(EventType.MOVE_USED, kinds)
        self.assertIs(b.player_creature, backup)

    def test_cannot_switch_to_creature_already_out(self):
        b = self.wild_battle([self.loader.get_creature(4), self.loader.get_creature(7)],
                             self.loader.get_creature(19))
        self.assertEqual(b.switch_creature(0)[0].event_type, EventType.INVALID_ACTION)


class TestMoveLearning(_Base):
    def test_new_move_learned_automatically_when_a_slot_is_free(self):
        mine = self.loader.get_creature(4, level=6)     # knows Scratch, Growl; Ember at 7
        mine.gain_xp(7 ** 3 - mine.xp - 1)              # one XP short of level 7

        b = self.wild_battle([mine], self.loader.get_creature(19, level=3))
        mine.modify_stat_stage("attack", 6)
        self.win_one_turn(b)

        self.assertTrue(mine.knows_move("ember"))
        self.assertIsNone(b.pending_move)

    def test_full_moveset_asks_which_move_to_forget(self):
        mine = self.loader.get_creature(4, level=12)     # Scratch, Growl, Ember
        mine.learn_move(self.loader.get_move("tackle"))  # now 4 moves; Bite comes at level 13
        self.assertEqual(len(mine.moves), 4)
        mine.gain_xp(13 ** 3 - mine.xp - 1)              # one XP short of level 13

        b = self.wild_battle([mine], self.loader.get_creature(19, level=5))
        mine.modify_stat_stage("attack", 6)
        self.win_one_turn(b)

        self.assertIsNotNone(b.pending_move)
        self.assertEqual(b.pending_move.id, "bite")
        old_first = mine.moves[0].id
        events = b.learn_pending_move(0)
        self.assertEqual(events[0].event_type, EventType.MOVE_LEARNED)
        self.assertTrue(mine.knows_move("bite"))
        self.assertFalse(mine.knows_move(old_first))
        self.assertIsNone(b.pending_move)

    def test_player_can_refuse_new_move(self):
        mine = self.loader.get_creature(4, level=12)
        mine.learn_move(self.loader.get_move("tackle"))
        mine.gain_xp(13 ** 3 - mine.xp - 1)
        before = [m.id for m in mine.moves]

        b = self.wild_battle([mine], self.loader.get_creature(19, level=5))
        mine.modify_stat_stage("attack", 6)
        self.win_one_turn(b)
        b.learn_pending_move(None)

        self.assertEqual([m.id for m in mine.moves], before)
        self.assertIsNone(b.pending_move)


class TestEventIds(_Base):
    def test_same_species_on_both_sides_are_told_apart(self):
        mine = self.loader.get_creature(4, level=10)
        wild = self.loader.get_creature(4, level=10)
        self.assertNotEqual(mine.uid, wild.uid)

        b = self.wild_battle([mine], wild)
        events = b.execute_move(0)
        hits = [e for e in events if e.event_type is EventType.DAMAGE_DEALT]
        self.assertTrue(hits)
        for e in hits:
            self.assertIn(e.data["target_uid"], (mine.uid, wild.uid))


class TestAfterBattle(_Base):
    def test_blackout_heals_party_and_costs_half_the_money(self):
        mon = self.loader.get_creature(4, level=5)
        mon.take_damage(999)
        t = Trainer("A", Party([mon]), money=1000)

        lost = t.black_out()

        self.assertEqual(lost, 500)
        self.assertEqual(t.money, 500)
        self.assertFalse(mon.is_fainted)

    def test_party_lists_creatures_ready_to_evolve(self):
        ready = self.loader.get_creature(4, level=16)
        not_ready = self.loader.get_creature(7, level=10)
        party = Party([ready, not_ready])
        self.assertEqual(party.ready_to_evolve(), (ready,))
        self.assertEqual(ready.evolves_into, 5)
        self.assertIsNone(self.loader.get_creature(6).evolves_into)


if __name__ == "__main__":
    unittest.main()
