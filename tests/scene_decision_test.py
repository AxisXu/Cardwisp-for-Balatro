"""开包、出牌、盲注的可核对依据；不调用模型。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scene_decision import build_pack_evidence, build_play_evidence, build_blind_evidence


class SceneDecisionTest(unittest.TestCase):
    def test_pack_checks_visible_options_and_slots_without_revealing_hidden_card(self):
        facts = build_pack_evidence({"phase": "pack", "jokers": 2, "slots": 2,
                                     "pack": {"type": "Buffoon", "choices_left": 1, "size": 3,
                                              "options": [{"key": "j_good", "name": "好牌", "set": "Joker",
                                                           "description": "+4 倍率", "position": 1},
                                                          {"hidden": True, "position": 2}]}})
        self.assertEqual(facts["choices_left"], 1)
        self.assertEqual(facts["options"][0]["slot_status"], "full")
        self.assertEqual(facts["options"][0]["effect_status"], "known")
        self.assertEqual(facts["options"][1], {"position": 2, "hidden": True})
        self.assertNotIn("j_secret", str(facts))

    def test_play_checks_score_gap_but_does_not_claim_exact_final_score(self):
        facts = build_play_evidence({"phase": "play", "blind": {"chips": 22000, "score": 17615},
                                     "hands_left": 3, "discards_left": 1,
                                     "current_hand": {"name": "Straight", "chips": 170, "mult": 16},
                                     "hand": [{"rank": "10", "selected": True}, {"hidden": True}],
                                     "poker_hands": {"Straight": {"level": 5, "played": 3,
                                                                  "chips": 70, "mult": 8}}})
        self.assertEqual(facts["score_needed"], 4385)
        self.assertEqual(facts["selected_positions"], [1])
        self.assertEqual(facts["hidden_hand_cards"], 1)
        self.assertIsNone(facts["verified_play_scores"])  # 有背面手牌时不计分
        self.assertEqual(facts["current_hand_preview"]["name"], "Straight")

    def test_play_lists_verified_scores_from_the_ported_scorer(self):
        def card(rank, suit, name, position):
            return {"position": position, "rank": rank, "suit": suit, "name": name, "key": "c_base",
                    "set": "Default", "description": "",
                    "values": {"bonus": 0, "perma_bonus": 0, "mult": 0, "x_mult": 1}}
        snapshot = {"phase": "play", "blind": {"chips": 300, "score": 0, "key": "bl_small", "name": "小盲注"},
                    "hands_left": 4, "discards_left": 3, "hands_played": 0, "money": 4, "slots": 5,
                    "hand": [card("Queen", "Spades", "Q♠", 1), card("Queen", "Hearts", "Q♥", 2),
                             card("3", "Diamonds", "3♦", 3)],
                    "owned": [{"key": "j_joker", "name": "小丑", "rarity": 1, "sell_cost": 1,
                               "description": "+4 倍率", "values": {"mult": 4}}],
                    "poker_hands": {"Pair": {"level": 1, "chips": 10, "mult": 2, "played": 0,
                                             "played_this_round": 0},
                                    "High Card": {"level": 1, "chips": 5, "mult": 1, "played": 0,
                                                  "played_this_round": 0}}}
        scores = build_play_evidence(snapshot)["verified_play_scores"]
        best = scores["top_plays"][0]
        self.assertEqual((best["positions"], best["cards"], best["hand_type"]), ([1, 2], ["Q♠", "Q♥"], "Pair"))
        self.assertEqual(best["score"], (10 + 10 + 10) * (2 + 4))  # 中文卡面也能算：小丑按 key 计分
        self.assertFalse(scores["best_clears_score_needed"])
        # Flint 改计分数学：按 key 认出来就不给数，名字是中文也一样。
        snapshot["blind"] = dict(snapshot["blind"], key="bl_flint", name="燧石")
        self.assertIsNone(build_play_evidence(snapshot)["verified_play_scores"])
        # 灵媒要求打满 5 张：按 key 认出后，不足 5 张的出牌确定是 0 分。
        snapshot["blind"] = dict(snapshot["blind"], key="bl_psychic", name="灵媒")
        scores = build_play_evidence(snapshot)["verified_play_scores"]
        self.assertEqual(scores["best_guaranteed_score"], 0)

    def test_blind_checks_visible_choices_and_skip_tags_only(self):
        facts = build_blind_evidence({"phase": "blind_select", "blind_on_deck": "Small",
                                      "blind_options": [{"slot": "Small", "chips": 800,
                                                         "reward": 3, "skip_tag": "优惠券标签"},
                                                        {"slot": "Big", "chips": 1200, "reward": 4}],
                                      "boss_reroll_cost": 10, "boss_reroll_available": False,
                                      "poker_hands": {"Pair": {"level": 2}},
                                      "vouchers": [{"key": "v_seed_money"}]})
        self.assertEqual(len(facts["visible_options"]), 2)
        self.assertEqual(facts["visible_options"][0]["skip_tag"], "优惠券标签")
        self.assertEqual(facts["boss_reroll"], {"cost": 10, "available": False})
        self.assertEqual(facts["run_info"]["poker_hands"]["Pair"]["level"], 2)
        self.assertEqual(facts["run_info"]["vouchers"][0]["key"], "v_seed_money")


if __name__ == "__main__":
    unittest.main()
