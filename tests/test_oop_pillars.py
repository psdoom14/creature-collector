"""Tests that demonstrate the four OOP pillars in the model layer.

Each test class maps to one pillar, so it can be pointed to in the project report.
"""
import random
import unittest

from src.data_loader import DataLoader
from src.model.bag import Bag
from src.model.battle import WildBattle as Battle
from src.model.events import EventType
from src.model.item import CatchBall, HealingItem, Item, ReviveItem, StatusCureItem
from src.model.move import DamagingMove, Move, PhysicalMove, SpecialMove, StatusMove
from src.model.move_effect import ChangeStat, HealUser, InflictStatus, MoveEffect
from src.model.pokedex import Pokedex
from src.model.status import Burn, Paralysis, Poison, Sleep, StatusCondition
from src.model.trainer import Party, Trainer


class _LoaderMixin:
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.chart = cls.loader.get_type_chart()


class TestEncapsulation(_LoaderMixin, unittest.TestCase):
    """State can be read but only changed through methods that enforce the rules."""

    def test_creature_state_is_read_only(self):
        c = self.loader.get_creature(4, level=5)
        for attr, value in [("current_hp", 999), ("level", 100), ("xp", 0), ("moves", ()),
                            ("status_effect", "burn"), ("name", "X")]:
            with self.subTest(attr=attr), self.assertRaises(AttributeError):
                setattr(c, attr, value)

    def test_hp_is_clamped_by_methods(self):
        c = self.loader.get_creature(4, level=5)
        c.take_damage(10_000)
        self.assertEqual(c.current_hp, 0)
        c.revive(1.0)
        c.heal(10_000)
        self.assertEqual(c.current_hp, c.max_hp)

    def test_moves_tuple_cannot_be_mutated_from_outside(self):
        c = self.loader.get_creature(4, level=5)
        with self.assertRaises((TypeError, AttributeError)):
            c.moves.append(self.loader.get_move("tackle"))  # type: ignore[attr-defined]

    def test_creature_never_knows_more_than_four_moves(self):
        c = self.loader.get_creature(6, level=50)
        for move_id in ("tackle", "scratch", "ember", "flamethrower", "growl"):
            c.learn_move(self.loader.get_move(move_id))
        self.assertLessEqual(len(c.moves), 4)

    def test_item_stock_only_changes_through_methods(self):
        potion = self.loader.get_item("potion", 2)
        with self.assertRaises(AttributeError):
            potion.quantity = 99
        with self.assertRaises(ValueError):
            potion.add_stock(-5)

    def test_party_and_bag_hide_their_collections(self):
        party = Party([self.loader.get_creature(4)])
        self.assertIsInstance(party.creatures, tuple)
        bag = Bag([self.loader.get_item("potion", 1)])
        self.assertIsInstance(bag.items, tuple)
        bag.use("potion", self.loader.get_creature(4))  # full HP: no effect, still 1 left
        self.assertTrue(bag.has("potion"))

    def test_trainer_cannot_overspend(self):
        t = Trainer("A", money=100)
        self.assertFalse(t.spend(500))
        self.assertEqual(t.money, 100)

    def test_pokedex_sets_are_frozen(self):
        dex = Pokedex()
        dex.register_caught(4)
        self.assertIsInstance(dex.caught, frozenset)


class TestAbstraction(unittest.TestCase):
    """Abstract base classes define a contract and can't be instantiated themselves."""

    def test_abstract_bases_cannot_be_instantiated(self):
        for abstract in (Move, DamagingMove, Item, StatusCondition, MoveEffect):
            with self.subTest(cls=abstract.__name__), self.assertRaises(TypeError):
                abstract()  # type: ignore[abstract]


class TestInheritance(unittest.TestCase):
    """Concrete classes extend shared base classes."""

    def test_hierarchies(self):
        cases = [
            (Move, [PhysicalMove, SpecialMove, StatusMove]),
            (DamagingMove, [PhysicalMove, SpecialMove]),
            (Item, [HealingItem, StatusCureItem, ReviveItem, CatchBall]),
            (StatusCondition, [Burn, Poison, Paralysis, Sleep]),
            (MoveEffect, [InflictStatus, HealUser, ChangeStat]),
        ]
        for base, subclasses in cases:
            for sub in subclasses:
                with self.subTest(base=base.__name__, sub=sub.__name__):
                    self.assertTrue(issubclass(sub, base))

    def test_subclasses_reuse_base_behaviour(self):
        # PP handling lives only in Move, yet every subclass has it.
        move = PhysicalMove("t", "Test", "Normal", power=40, accuracy=100, pp=2)
        self.assertTrue(move.use())
        self.assertEqual(move.current_pp, 1)


class TestPolymorphism(_LoaderMixin, unittest.TestCase):
    """The same call does different things depending on the object's class."""

    def setUp(self):
        random.seed(42)

    def test_moves_pick_their_own_stats(self):
        c = self.loader.get_creature(6, level=30)
        c.modify_stat_stage("attack", +2)
        physical = self.loader.get_move("scratch")
        special = self.loader.get_move("ember")
        self.assertEqual(physical.attack_stat(c), c.attack)
        self.assertEqual(special.attack_stat(c), c.sp_attack)
        self.assertNotEqual(physical.attack_stat(c), special.attack_stat(c))

    def test_statuses_behave_differently_on_the_same_calls(self):
        c = self.loader.get_creature(7, level=20)
        self.assertGreater(Burn().on_turn_end(c)[0], 0)
        self.assertGreater(Poison().on_turn_end(c)[0], 0)
        self.assertEqual(Paralysis().on_turn_end(c)[0], 0)
        self.assertEqual(Paralysis().modify_speed(100), 50)
        self.assertEqual(Burn().modify_speed(100), 100)
        self.assertFalse(Sleep(turns=1).before_move(c)[0])

    def test_items_respond_to_use_in_battle_in_their_own_way(self):
        mine = self.loader.get_creature(6, level=50)
        mine.take_damage(30)
        trainer = Trainer("A", Party([mine]))
        trainer.add_item(self.loader.get_item("potion", 1), 1)
        trainer.add_item(self.loader.get_item("ultra_ball", 1), 1)
        wild = self.loader.get_creature(19, level=2)
        battle = Battle(trainer, wild, self.chart)

        potion_events = battle.use_item("potion")
        self.assertEqual(potion_events[0].event_type, EventType.ITEM_USED)

        ball_events = battle.use_item("ultra_ball")
        self.assertEqual(ball_events[0].event_type, EventType.BALL_THROWN)

    def test_effects_share_one_interface(self):
        user = self.loader.get_creature(4, level=10)
        target = self.loader.get_creature(7, level=10)
        user.take_damage(10)
        effects = [InflictStatus("paralyze", 100), HealUser("heal", 100),
                   ChangeStat("stat_lower_attack", 100, stat="attack", stages=-1)]
        kinds = [effect.apply(user, target)[0].event_type for effect in effects]
        self.assertEqual(kinds, [EventType.STATUS_APPLIED, EventType.HEAL, EventType.STAT_CHANGE])


if __name__ == "__main__":
    unittest.main()
