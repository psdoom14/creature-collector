"""Shops, item balls, gift givers, the player's home and the new houses."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from src.data_loader import DataLoader
from src.model.direction import Direction
from src.model.entities import GiftGiver, Healer, Interactable, ItemBall, Shopkeeper
from src.model.errors import RuleViolation
from src.model.game_state import GameState
from src.model.shop import Shop
from src.model.story import StoryFlags
from src.model.trainer import Trainer
from src.model.world import Explorer, Location


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()
        self.loader.load_all()
        self.shop = Shop(["poke_ball", "potion"], self.loader.get_item)
        self.trainer = Trainer("ASH", money=1000)

    def test_buying_spends_money_and_adds_items(self):
        result = self.shop.buy(self.trainer, "potion", 3)
        self.assertTrue(result.success)
        self.assertEqual(self.trainer.money, 1000 - 3 * 300)
        self.assertEqual(self.trainer.get_item("potion").quantity, 3)

    def test_cannot_buy_without_enough_money(self):
        result = self.shop.buy(self.trainer, "poke_ball", 6)   # $1200
        self.assertFalse(result.success)
        self.assertEqual(self.trainer.money, 1000)
        self.assertFalse(self.trainer.has_item("poke_ball"))

    def test_max_affordable(self):
        self.assertEqual(self.shop.max_affordable(self.trainer, "poke_ball"), 5)

    def test_selling_pays_half_price(self):
        self.trainer.add_item(self.loader.get_item("revive", 2), 2)
        result = self.shop.sell(self.trainer, "revive", 1)   # any priced item can be sold, not just the stock
        self.assertTrue(result.success)
        self.assertEqual(self.trainer.money, 1000 + 750)
        self.assertEqual(self.trainer.get_item("revive").quantity, 1)

    def test_selling_more_than_you_have_sells_what_you_have(self):
        self.trainer.add_item(self.loader.get_item("potion", 1), 1)
        self.shop.sell(self.trainer, "potion", 5)
        self.assertEqual(self.trainer.money, 1000 + 150)
        self.assertFalse(self.trainer.has_item("potion"))

    def test_rules(self):
        with self.assertRaises(RuleViolation):
            self.shop.buy(self.trainer, "ultra_ball", 1)       # not in stock
        with self.assertRaises(RuleViolation):
            self.shop.buy(self.trainer, "potion", 0)
        free = self.loader.get_item("potion")
        free._price = 0
        with self.assertRaises(RuleViolation):
            Shop(["potion"], lambda item_id, qty: free)          # an unpriced item can't be stocked

    def test_every_item_has_a_price(self):
        for data in self.loader.get_all_items():
            self.assertGreater(self.loader.get_item(data["id"]).price, 0, data["id"])


class MapEntityTests(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()
        self.loader.load_all()
        self.state = GameState(Trainer("ASH"))

    def test_item_ball_is_picked_up_once_then_stops_blocking(self):
        ball = Interactable.from_data({"kind": "item_ball", "id": "t1", "x": 1, "y": 1, "item": "potion", "quantity": 2})
        self.assertIsInstance(ball, ItemBall)
        self.assertTrue(ball.is_present(self.state))
        first = ball.interact(self.state, Direction.UP)
        self.assertEqual(first.effect, "give_items")
        self.assertEqual(first.data["items"], {"potion": 2})
        self.assertFalse(ball.is_present(self.state))
        self.assertIsNone(ball.interact(self.state, Direction.UP).effect)

    def test_gift_giver_gives_once(self):
        npc = Interactable.from_data({"kind": "gift_npc", "id": "g", "x": 0, "y": 0, "name": "FEN",
                                      "lines": ["Here!"], "gift": {"great_ball": 3}, "after_lines": ["Bye"]})
        self.assertIsInstance(npc, GiftGiver)
        self.assertEqual(npc.interact(self.state, Direction.UP).effect, "give_items")
        again = npc.interact(self.state, Direction.UP)
        self.assertIsNone(again.effect)
        self.assertEqual(again.lines, ("Bye",))

    def test_shopkeeper_opens_the_shop(self):
        clerk = Interactable.from_data({"kind": "shopkeeper", "x": 0, "y": 0, "stock": ["potion"]})
        self.assertIsInstance(clerk, Shopkeeper)
        result = clerk.interact(self.state, Direction.UP)
        self.assertEqual(result.effect, "open_shop")
        self.assertEqual(result.data["stock"], ("potion",))

    def test_mom_heals_with_her_own_words(self):
        world = self.loader.load_world()
        mom = next(e for e in world.get("player_home").entities if isinstance(e, Healer))
        self.assertEqual(mom.name, "MOM")
        result = mom.interact(self.state, Direction.UP)
        self.assertEqual(result.effect, "healed")
        self.assertNotIn("Come back any time!", result.lines)

    def test_every_shop_in_the_world_can_be_opened(self):
        world = self.loader.load_world()
        clerks = [e for m in world.map_ids for e in world.get(m).entities if isinstance(e, Shopkeeper)]
        self.assertTrue(clerks)
        for clerk in clerks:
            Shop(clerk.stock, self.loader.get_item)   # raises if any stock item is unknown or unpriced

    def test_every_house_door_leads_somewhere(self):
        world = self.loader.load_world()
        for map_id in world.map_ids:
            m = world.get(map_id)
            for y in range(m.height):
                for x in range(m.width):
                    if m.tile_name(x, y) in ("house_door", "center_door", "gym_door", "shop_door"):
                        self.assertIsNotNone(m.warp_at(x, y), f"{map_id} door at {x},{y} doesn't open")

    def test_walking_onto_a_picked_up_ball(self):
        world = self.loader.load_world()
        flags = StoryFlags()
        explorer = Explorer(world, Location("route_1", 13, 1), Direction.RIGHT, flags=flags)
        self.assertFalse(explorer.step(Direction.RIGHT).moved)          # the ball at (14, 1) blocks
        self.assertIsInstance(explorer.facing_target(), ItemBall)
        flags.set("picked_route1_poke_balls")
        self.assertIsNone(explorer.facing_target())
        self.assertTrue(explorer.step(Direction.RIGHT).moved)


if __name__ == "__main__":
    unittest.main()


class ShopScreenTests(unittest.TestCase):
    """Drive the real shop screen with key presses, from talking to the clerk to selling."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        import pygame
        from src.ui import components
        from src.ui.engine import GameEngine
        from src.ui.overworld_scene import OverworldScene
        pygame.init()
        self.pygame, self.components = pygame, components
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = GameEngine(save_path=Path(self.tmp.name) / "save.json")
        self.engine.new_game()
        self.ow = OverworldScene(self.engine)
        self.engine.push_scene(self.ow)
        components.reset_overflow_log()

    def tearDown(self):
        self.tmp.cleanup()

    def press(self, scene, key, times=1):
        for _ in range(times):
            scene.handle_event(self.pygame.event.Event(self.pygame.KEYDOWN, key=key))
            scene.update(1.0)

    def draw(self, scene):
        scene.draw(self.engine.native_surface)

    def test_buy_and_sell_through_the_screen(self):
        from src.ui.shop_scene import ShopScene
        pg = self.pygame
        trainer = self.engine.game_state.trainer
        trainer.earn(5000 - trainer.money)
        self.ow.teleport(Location("brookhaven_shop", 2, 4), Direction.UP)
        self.press(self.ow, pg.K_z, 3)                   # talk to the clerk, close the greeting
        shop = self.engine.scene_stack[-1]
        self.assertIsInstance(shop, ShopScene)
        self.draw(shop)

        self.press(shop, pg.K_z)                          # BUY
        for _ in range(len(shop.shop.catalog)):           # every row and description fits
            self.draw(shop)
            self.press(shop, pg.K_DOWN)
        before = trainer.get_item("great_ball").quantity if trainer.has_item("great_ball") else 0
        self.press(shop, pg.K_DOWN)                        # great ball (wrapped back to the top, then down one)
        self.press(shop, pg.K_z)
        self.press(shop, pg.K_UP, 2)                       # x3
        self.draw(shop)
        self.press(shop, pg.K_z)
        self.draw(shop)
        self.assertEqual(trainer.get_item("great_ball").quantity, before + 3)
        self.assertEqual(trainer.money, 5000 - 3 * 600)

        self.press(shop, pg.K_z)                          # close the message
        self.press(shop, pg.K_x)                          # back to BUY/SELL/QUIT
        self.press(shop, pg.K_DOWN)
        self.press(shop, pg.K_z)                          # SELL
        self.draw(shop)
        first = trainer.bag.items[0]
        count = first.quantity
        self.press(shop, pg.K_z)
        self.press(shop, pg.K_z)                          # sell one
        self.assertEqual(trainer.get_item(first.id).quantity if trainer.has_item(first.id) else 0, count - 1)
        self.press(shop, pg.K_z)
        self.press(shop, pg.K_x)
        self.press(shop, pg.K_x)                          # leave the shop
        self.assertIs(self.engine.scene_stack[-1], self.ow)
        self.assertEqual(self.components.overflow_log(), [], "text drawn wider than its box")
