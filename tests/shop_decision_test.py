"""商店决策依据：只核对公开数字，不替模型评估卡牌强度。"""

import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "scripts/shop_decision.py"
spec = importlib.util.spec_from_file_location("shop_decision", path)
shop_decision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shop_decision)


class ShopDecisionTest(unittest.TestCase):
    def test_baseball_synergy_counts_only_confirmed_uncommon_jokers(self):
        snapshot = {
            "phase": "shop", "money": 12, "jokers": 4, "slots": 5,
            "economy": {"bankrupt_at": 0, "reroll_cost": 5}, "shop": [],
            "owned": [
                {"position": 1, "key": "j_baseball", "set": "Joker",
                 "rarity_label": "RARE", "values": {"extra": 1.5}},
                {"position": 2, "key": "j_dusk", "set": "Joker", "rarity_label": "UNCOMMON"},
                {"position": 3, "key": "j_fibonacci", "set": "Joker", "rarity_label": "UNCOMMON"},
                {"position": 4, "key": "j_unknown", "set": "Joker"},
            ],
        }
        facts = shop_decision.build_shop_evidence(snapshot, 2)
        self.assertEqual(facts["baseball_synergy"], {
            "per_uncommon_x_mult": 1.5,
            "confirmed_uncommon_positions": [2, 3],
            "unknown_rarity_positions": [4],
            "confirmed_x_mult": 2.25,
        })
        snapshot["owned"].append({"position": 5, "key": "j_baseball", "set": "Joker",
                                  "rarity_label": "RARE", "values": {"extra": 1.5}})
        self.assertNotIn("baseball_synergy", shop_decision.build_shop_evidence(snapshot, 3))

    def test_purchase_facts_use_current_price_credit_and_interest_cap(self):
        snapshot = {
            "phase": "shop", "money": 35, "jokers": 4, "slots": 5,
            "consumables": [], "consumable_slots": 2,
            "economy": {"bankrupt_at": -5, "interest_per_5": 1, "interest_cap": 25,
                        "no_interest": False, "reroll_cost": 6, "free_rerolls": 0},
            "shop": [
                {"key": "j_a", "name": "甲", "set": "Joker", "cost": 6,
                 "description": "每回合加倍率", "current_bonus": {"kind": "add_mult", "value": 8}},
                {"key": "j_b", "name": "乙", "set": "Joker", "cost": 41,
                 "description_unresolved": True},
                {"key": "p_arcana_normal_1", "name": "秘术包", "set": "Booster", "cost": 4},
            ],
        }
        facts = shop_decision.build_shop_evidence(snapshot, 7)
        self.assertIn("shop_state_version", facts)
        self.assertEqual(facts["shop_state_version"], 7)
        self.assertEqual(facts["interest_at_current_balance"], 5)
        self.assertEqual(facts["offers"][0]["balance_after_direct_cost"], 29)
        self.assertEqual(facts["offers"][0]["interest_if_balance_unchanged"], 5)
        self.assertEqual(facts["offers"][0]["slot_status"], "available")
        self.assertEqual(facts["offers"][0]["current_bonus"], {"kind": "add_mult", "value": 8})
        self.assertFalse(facts["offers"][1]["affordable"])
        self.assertEqual(facts["offers"][1]["slot_status"], "available")
        self.assertEqual(facts["offers"][1]["effect_status"], "uncertain")
        self.assertEqual(facts["offers"][2]["contents_status"], "unopened_unknown")
        self.assertEqual(facts["reroll"]["balance_after_direct_cost"], 29)

    def test_free_reroll_full_slots_and_unknown_interest_stay_explicit(self):
        snapshot = {
            "phase": "shop", "money": 4, "jokers": 5, "slots": 5,
            "consumables": [{"key": "c_a"}], "consumable_slots": 1,
            "economy": {"bankrupt_at": 0, "free_rerolls": 1, "reroll_cost": 0},
            "shop": [{"key": "j_a", "set": "Joker", "cost": 2},
                     {"key": "c_b", "set": "Tarot", "cost": 3}],
        }
        facts = shop_decision.build_shop_evidence(snapshot, 8)
        self.assertIn("reroll", facts)
        self.assertEqual(facts["reroll"]["cost_now"], 0)
        self.assertEqual(facts["reroll"]["balance_after_direct_cost"], 4)
        self.assertIsNone(facts["interest_at_current_balance"])
        self.assertIsNone(facts["offers"][0]["interest_if_balance_unchanged"])
        self.assertEqual(facts["offers"][0]["slot_status"], "full")
        self.assertEqual(facts["offers"][1]["slot_status"], "full")
        self.assertEqual(facts["offers"][0]["effect_status"], "unknown")

    def test_displayed_reroll_cost_wins_if_free_count_disagrees(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "money": 4,
            "economy": {"bankrupt_at": 0, "free_rerolls": 1, "reroll_cost": 9},
            "shop": [],
        }, 1)
        self.assertEqual(facts["reroll"]["cost_now"], 9)
        self.assertFalse(facts["reroll"]["affordable"])

    def test_negative_edition_adds_purchase_space_at_full_capacity(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "money": 10, "jokers": 5, "slots": 5,
            "consumables": [{"key": "c_a"}], "consumable_slots": 1,
            "economy": {"bankrupt_at": 0},
            "shop": [{"key": "j_neg", "set": "Joker", "edition": "negative", "cost": 5},
                     {"key": "c_neg", "set": "Tarot", "edition": "negative", "cost": 5},
                     {"key": "j_plain", "set": "Joker", "cost": 5}],
        }, 1)
        self.assertEqual([offer["slot_status"] for offer in facts["offers"]],
                         ["available", "available", "full"])

    def test_free_card_and_reroll_can_be_used_below_credit_floor(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "money": -6, "jokers": 0, "slots": 1,
            "economy": {"bankrupt_at": -5, "reroll_cost": 0, "free_rerolls": 1},
            "shop": [{"key": "j_free", "set": "Joker", "cost": 0},
                     {"key": "v_free", "set": "Voucher", "cost": 0},
                     {"key": "p_free", "set": "Booster", "cost": 0}],
        }, 1)
        self.assertEqual([offer["affordable"] for offer in facts["offers"]],
                         [True, False, True])
        self.assertTrue(facts["reroll"]["affordable"])

    def test_missing_shop_fields_never_turn_into_free_or_affordable(self):
        facts = shop_decision.build_shop_evidence({"phase": "shop", "shop": [
            {"key": "j_a", "set": "Joker"}]}, 1)
        self.assertIn("offers", facts)
        self.assertIsNone(facts["offers"][0]["price"])
        self.assertIsNone(facts["offers"][0]["affordable"])
        self.assertIsNone(facts["reroll"]["cost_now"])
        self.assertIn("money", facts["missing"])
        self.assertIn("reroll_cost", facts["missing"])

    def test_visible_hand_size_value_is_not_discarded_from_shop_evidence(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "shop": [{"key": "j_juggler", "set": "Joker", "cost": 4,
                                        "description": "手牌上限+1", "values": {"h_size": 1}}]}, 1)
        self.assertEqual(facts["offers"][0]["visible_values"], {"h_size": 1})
        self.assertEqual(facts["offers"][0]["effect_status"], "known")

    def test_full_joker_slot_lists_legal_replacements_with_direct_economy(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "money": 23, "jokers": 3, "slots": 3,
            "economy": {"bankrupt_at": 0, "interest_per_5": 1,
                        "interest_cap": 25, "no_interest": False},
            "owned": [
                {"position": 1, "key": "j_first", "name": "旧牌", "set": "Joker",
                 "sell_cost": 3, "current_bonus": {"kind": "add_mult", "value": 8}},
                {"position": 2, "key": "j_eternal", "name": "永恒牌", "set": "Joker",
                 "sell_cost": 7, "eternal": True},
                {"position": 3, "key": "j_negative", "name": "负片牌", "set": "Joker",
                 "sell_cost": 2, "edition": "negative"},
            ],
            "shop": [{"position": 1, "key": "j_new", "name": "新牌", "set": "Joker",
                      "cost": 6, "description": "+倍率"}],
        }, 2)
        offer = facts["offers"][0]
        self.assertEqual(offer["slot_status"], "full")
        self.assertEqual(len(offer["swap_options"]), 1)
        swap = offer["swap_options"][0]
        self.assertEqual(swap["sell_key"], "j_first")
        self.assertEqual(swap["sell_proceeds"], 3)
        self.assertEqual(swap["balance_after_direct_exchange"], 20)
        self.assertEqual(swap["interest_if_balance_unchanged"], 4)
        self.assertTrue(swap["affordable"])

    def test_unknown_sale_proceeds_are_not_assumed_zero(self):
        facts = shop_decision.build_shop_evidence({
            "phase": "shop", "money": 1, "jokers": 1, "slots": 1,
            "economy": {"bankrupt_at": 0},
            "owned": [{"position": 1, "key": "j_old", "name": "旧牌", "set": "Joker"}],
            "shop": [{"key": "j_new", "set": "Joker", "cost": 4}],
        }, 1)
        self.assertEqual(facts["offers"][0]["swap_options"], [])
        self.assertIn("owned_joker_sell_cost_1", facts["missing"])


if __name__ == "__main__":
    unittest.main()
