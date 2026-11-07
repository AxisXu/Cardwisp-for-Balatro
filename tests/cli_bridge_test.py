"""不调用远端模型，验证本机桥接的协议与 CLI 约束。"""

from http.server import HTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


path = Path(__file__).resolve().parents[1] / "scripts/cli_bridge.py"
spec = importlib.util.spec_from_file_location("cli_bridge", path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTest(unittest.TestCase):
    def test_play_goal_defaults_to_clear_persists_and_changes_advice_context(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            state = bridge.SessionState(settings_path=path)
            state.update_snapshot("r1", {"phase": "shop", "ante": 4, "shop": []}, "zh_CN")
            self.assertEqual(state.view()["settings"]["play_goal"], "clear")
            prompts = []
            state.ask("现在该攒钱吗？", lambda prompt, *_: prompts.append(prompt) or "建议")
            self.assertIn("Ante 8", prompts[-1][0]["content"])

            with patch.object(bridge, "AVAILABLE_GOALS", ("clear", "endless")):
                state.update_settings({"play_goal": "endless"})
                restarted = bridge.SessionState(settings_path=path)
            restarted.update_snapshot("r2", {"phase": "shop", "ante": 4, "shop": []}, "zh_CN")
            self.assertEqual(restarted.view()["settings"]["play_goal"], "endless")
            restarted.ask("现在该攒钱吗？", lambda prompt, *_: prompts.append(prompt) or "建议")
            self.assertIn("endless", prompts[-1][0]["content"].lower())
            with self.assertRaises(ValueError):
                restarted.update_settings({"play_goal": "unknown"})

    def test_changing_play_goal_discards_answer_for_previous_goal(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {"phase": "shop", "shop": []}, "zh_CN")

            def runner(*_):
                state.update_settings({"play_goal": "endless"})
                return "按通关目标的旧建议"

            with patch.object(bridge, "AVAILABLE_GOALS", ("clear", "endless")), \
                    self.assertRaisesRegex(RuntimeError, "goal_changed"):
                state.ask("怎么买？", runner)
            self.assertNotIn("按通关目标的旧建议", [entry["text"] for entry in state.view()["messages"]])
            self.assertFalse(state.view()["pending"])

    def test_other_scenes_receive_checked_evidence_and_scene_specific_instructions(self):
        examples = [
            ({"phase": "pack", "pack": {"type": "Buffoon", "choices_left": 1,
                                         "options": [{"key": "j_new", "set": "Joker"}]}},
              "pack_evidence", "visible pack"),
            ({"phase": "play", "blind": {"chips": 300, "score": 100},
              "hand": [{"rank": "Ace"}], "hands_left": 2, "discards_left": 1},
             "play_evidence", "final score"),
            ({"phase": "blind_select", "blind_options": [{"slot": "Small", "chips": 300}],
              "blind_on_deck": "Small"}, "blind_evidence", "skip"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            for index, (snapshot, evidence_key, instruction) in enumerate(examples, 1):
                state.update_snapshot("r1", {**snapshot, "snapshot_revision": index}, "zh_CN")
                seen = []
                state.ask("怎么选？", lambda prompt, *_: seen.append(prompt) or "建议")
                self.assertIn(instruction, seen[0][0]["content"])
                context = json.loads(seen[0][-2]["content"].removeprefix("Latest visible state JSON: "))
                self.assertIn(evidence_key, context)
                self.assertNotIn("shop_evidence", context)

    def test_pack_and_play_change_during_reply_discard_outdated_advice(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            pack = {"phase": "pack", "pack": {"choices_left": 1,
                                                "options": [{"key": "j_old"}]}}
            state.update_snapshot("r1", pack, "zh_CN")
            with self.assertRaisesRegex(RuntimeError, "scene_changed"):
                state.ask("选哪张？", lambda *_: state.update_snapshot(
                    "r1", {**pack, "pack": {"choices_left": 1,
                                             "options": [{"key": "j_new"}]}}, "zh_CN") or "旧卡")
            play = {"phase": "play", "blind": {"score": 0, "chips": 300},
                    "hand": [{"rank": "Ace", "selected": False}]}
            state.update_snapshot("r1", play, "zh_CN")
            with self.assertRaisesRegex(RuntimeError, "scene_changed"):
                state.ask("这手怎么打？", lambda *_: state.update_snapshot(
                    "r1", {**play, "hand": [{"rank": "King", "selected": True}]}, "zh_CN") or "打 A")
            self.assertNotIn("旧卡", [m["text"] for m in state.view()["messages"]])
            self.assertNotIn("打 A", [m["text"] for m in state.view()["messages"]])

    def test_pack_waits_for_candidate_cards_before_using_model(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {"phase": "pack", "pack": {"choices_left": 1,
                                                                     "options": []}}, "zh_CN")
            called = []
            with self.assertRaisesRegex(RuntimeError, "scene_loading"):
                state.ask("这三张选哪张？", lambda *_: called.append(True) or "随便选")
            self.assertEqual(called, [])

    def test_one_time_session_restore_keeps_chat_during_service_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".restore-once.json"
            path.write_text(json.dumps({"run_id": "r1", "snapshot": {"phase": "shop", "shop": []},
                                        "language": "zh_CN", "messages": [{"role": "user", "text": "刚才怎么买？"},
                                                                            {"role": "assistant", "text": "先保留金币"}],
                                        "prompt_used": True}), encoding="utf-8")
            path.chmod(0o600)
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            self.assertTrue(state.restore_once(path))
            self.assertFalse(path.exists())
            self.assertEqual([m["text"] for m in state.view()["messages"]], ["刚才怎么买？", "先保留金币"])
            self.assertTrue(state.view()["connected"])

    def test_chinese_answers_get_game_terminology_english_does_not(self):
        # 人机实测里中文回答出现过「对打到 Ante 8 帮助最小」：英文提示词里的术语被原样抄进了中文。
        for language, expected in (("zh_CN", True), ("zh_TW", False), ("ja", False), ("en-us", False)):
            with tempfile.TemporaryDirectory() as temp:
                state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
                state.update_snapshot("r1", {"phase": "shop", "snapshot_revision": 1, "shop": []}, language)
                calls = []
                state.ask("怎么选？", lambda messages, *_: calls.append(messages) or "好")
                system = calls[0][0]["content"]
                self.assertEqual("Ante=底注" in system, expected, language)
                self.assertEqual("Mult=倍率" in system, expected, language)

    def test_reroll_uses_new_shop_over_previous_chat_and_rejects_late_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            old = {"phase": "shop", "snapshot_revision": 1, "economy": {"reroll_cost": 5},
                   "shop": [{"key": "j_faceless", "name": "无面小丑", "cost": 5}]}
            new = {"phase": "shop", "snapshot_revision": 2, "economy": {"reroll_cost": 6},
                   "shop": [{"key": "j_sixth_sense", "name": "第六感", "cost": 6},
                            {"key": "j_crafty", "name": "精明小丑", "cost": 4}]}
            state.update_snapshot("r1", old, "zh_CN")
            state.ask("旧商店怎么选？", lambda *_: "先不买无面小丑")
            state.update_snapshot("r1", new, "zh_CN")
            state.update_snapshot("r1", old, "zh_CN")  # 延迟抵达的旧版发布不能覆盖新局面。
            self.assertEqual(state.view()["snapshot"]["shop"][0]["name"], "第六感")
            self.assertEqual(state.view()["shop_state_version"], 2)
            calls = []
            state.ask("重掷后的小丑怎么选？", lambda messages, *_: calls.append(messages) or "看第六感")
            prompt = calls[0]
            self.assertIn("current shop", prompt[0]["content"])
            self.assertIn("第六感", prompt[-2]["content"])
            self.assertIn("精明小丑", prompt[-2]["content"])
            self.assertIn("无面小丑", prompt[-2]["content"])
            self.assertEqual(prompt[-1]["content"], "重掷后的小丑怎么选？")
            context = json.loads(prompt[-2]["content"].removeprefix("Latest visible state JSON: "))
            self.assertEqual([offer["key"] for offer in context["shop_evidence"]["offers"]],
                             ["j_sixth_sense", "j_crafty"])
            self.assertEqual(state.view()["messages"][-1]["shop_state_version"], 2)

    def test_shop_question_receives_checked_facts_from_its_current_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {"phase": "shop", "snapshot_revision": 3, "money": 12,
                                         "jokers": 1, "slots": 2, "consumables": [], "consumable_slots": 2,
                                         "economy": {"bankrupt_at": 0, "interest_per_5": 1,
                                                     "interest_cap": 25, "no_interest": False,
                                                     "reroll_cost": 5, "free_rerolls": 0},
                                         "shop": [{"key": "j_test", "name": "测试小丑",
                                                   "set": "Joker", "cost": 4,
                                                   "description": "+4 倍率"}]}, "zh_CN")
            captured = []
            state.ask("这个商店怎么选？", lambda prompt, *_: captured.append(prompt) or "可以买")
            prompt = captured[0]
            context = json.loads(prompt[-2]["content"].removeprefix("Latest visible state JSON: "))
            self.assertEqual(context["shop_evidence"]["offers"][0]["balance_after_direct_cost"], 8)
            self.assertEqual(context["shop_evidence"]["offers"][0]
                             ["interest_change_if_balance_unchanged"], -1)
            self.assertEqual(context["shop_evidence"]["reroll"]["cost_now"], 5)
            self.assertEqual(context["shop_evidence"]["shop_state_version"], context["shop_state_version"])
            self.assertIn("shop_evidence", prompt[0]["content"])

    def test_full_shop_prompts_model_to_compare_keep_and_concrete_swap(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {
                "phase": "shop", "snapshot_revision": 1, "money": 20,
                "jokers": 1, "slots": 1,
                "economy": {"bankrupt_at": 0, "interest_per_5": 1,
                            "interest_cap": 25, "no_interest": False},
                "owned": [{"position": 1, "key": "j_old", "name": "旧牌",
                           "set": "Joker", "sell_cost": 3}],
                "shop": [{"key": "j_new", "name": "新牌", "set": "Joker",
                          "cost": 6, "description": "新效果"}],
            }, "zh_CN")
            captured = []
            state.ask("这张新牌值得替换吗？", lambda prompt, *_: captured.append(prompt) or "可以比较")
            prompt = captured[0]
            context = json.loads(prompt[-2]["content"].removeprefix("Latest visible state JSON: "))
            self.assertEqual(context["shop_evidence"]["offers"][0]["swap_options"][0]
                             ["balance_after_direct_exchange"], 17)
            self.assertIn("compare keeping", prompt[0]["content"])

    def test_shop_change_during_model_reply_discards_outdated_advice(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            old = {"phase": "shop", "snapshot_revision": 1,
                   "shop": [{"key": "j_old", "cost": 5}]}
            new = {"phase": "shop", "snapshot_revision": 2,
                   "shop": [{"key": "j_new", "cost": 6}]}
            state.update_snapshot("r1", old, "zh_CN")

            def reply(*_):
                state.update_snapshot("r1", new, "zh_CN")
                return "买旧小丑"

            with self.assertRaisesRegex(RuntimeError, "shop_changed"):
                state.ask("这个商店怎么选？", reply)
            self.assertFalse(state.view()["pending"])
            self.assertNotIn("买旧小丑", [item["text"] for item in state.view()["messages"]])

    def test_money_change_during_shop_reply_also_discards_advice(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            snapshot = {"phase": "shop", "money": 10,
                        "shop": [{"key": "j_same", "cost": 6}]}
            state.update_snapshot("r1", snapshot, "zh_CN")

            def reply(*_):
                state.update_snapshot("r1", {**snapshot, "money": 4}, "zh_CN")
                return "可以买"

            with self.assertRaisesRegex(RuntimeError, "shop_changed"):
                state.ask("买吗？", reply)
            self.assertEqual(state.view()["messages"][-1]["text"], "shop_changed")

    def test_hover_only_change_does_not_discard_shop_reply(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            snapshot = {"phase": "shop", "money": 10,
                        "shop": [{"key": "j_same", "cost": 6, "selected": False}]}
            state.update_snapshot("r1", snapshot, "zh_CN")

            def reply(*_):
                state.update_snapshot("r1", {**snapshot, "snapshot_revision": 2,
                                             "shop": [{"key": "j_same", "cost": 6, "selected": True}]},
                                      "zh_CN")
                return "可以买这张"

            self.assertEqual(state.ask("怎么买？", reply), "可以买这张")
            self.assertEqual(state.view()["shop_state_version"], 1)

    def test_same_card_price_with_new_edition_counts_as_new_shop_offer(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            base = {"phase": "shop", "money": 10,
                    "economy": {"reroll_cost": 5},
                    "shop": [{"key": "j_same", "cost": 6, "edition": "foil"}]}
            state.update_snapshot("r1", base, "zh_CN")
            state.update_snapshot("r1", {**base, "shop": [{"key": "j_same", "cost": 6,
                                                          "edition": "polychrome"}]}, "zh_CN")
            self.assertEqual(state.view()["shop_state_version"], 2)

    def test_http_session_sync_and_browser_page(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            calls = []

            def runner(messages, model, effort):
                calls.append((model, effort))
                return "先看效果"

            opened = []
            server = HTTPServer((bridge.HOST, 0), bridge.make_handler(
                runner=runner, state=state, companion_opener=lambda: opened.append(True) or "native"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://{bridge.HOST}:{server.server_port}"

            def post(route, body, origin=None):
                headers = {"Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                request = Request(base + route, data=json.dumps(body).encode(), headers=headers)
                try:
                    with urlopen(request, timeout=2) as response:
                        return response.status, json.load(response)
                except HTTPError as exc:
                    return exc.code, json.load(exc)

            try:
                with urlopen(base + "/", timeout=2) as response:
                    self.assertIn("Cardwisp", response.read().decode())
                status, _ = post("/v1/session/snapshot", {"run_id": "r1", "snapshot": {"money": 7}, "language": "zh_CN"})
                self.assertEqual(status, 200)
                status, result = post("/v1/session/settings", {"model": "gpt-6-luna", "effort": "medium"}, origin=base)
                self.assertEqual(status, 200)
                self.assertEqual(result["settings"]["model"], "gpt-6-luna")
                status, _ = post("/v1/companion/open", [], origin=base)
                self.assertEqual(status, 400)
                status, result = post("/v1/companion/open", {"source": "game"}, origin=base)
                self.assertEqual((status, result["kind"], opened), (200, "native", [True]))
                status, result = post("/v1/session/message", {"question": "买吗？"}, origin=base)
                self.assertEqual(status, 200)
                self.assertEqual(result["choices"][0]["message"]["content"], "先看效果")
                self.assertEqual(calls, [("gpt-6-luna", "medium")])
                with urlopen(base + "/v1/session", timeout=2) as response:
                    self.assertEqual(len(json.load(response)["messages"]), 2)
                with self.assertRaises(HTTPError) as denied:
                    urlopen(Request(base + "/v1/session", headers={"Host": "attacker.example"}), timeout=2)
                self.assertEqual(denied.exception.code, 403)
                status, _ = post("/v1/session/settings", {"model": "gpt-6-astra"}, origin="https://evil.example")
                self.assertEqual(status, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_shared_session_and_model_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("run-1", {"phase": "shop", "money": 7,
                                            "economy": {"reroll_cost": 5},
                                            "owned": [{"key": "j_trousers", "current_bonus":
                                                       {"kind": "add_mult", "value": 4, "per_trigger": 2}}]}, "zh_CN")
            self.assertFalse(state.view()["prompt_used"])
            shop_scene = state.view()["scene_id"]
            state.update_settings({"model": "gpt-6-luna", "effort": "medium", "display_mode": "outside"})
            calls = []

            def runner(messages, model, effort):
                calls.append((messages, model, effort))
                return "先保留金币"

            answer = state.ask("怎么买？", runner)
            self.assertEqual(answer, "先保留金币")
            self.assertEqual(calls[0][1:], ("gpt-6-luna", "medium"))
            self.assertIn('"reroll_cost":5', calls[0][0][1]["content"])
            self.assertIn("description_unresolved", calls[0][0][0]["content"])
            self.assertIn('"current_bonus":{"kind":"add_mult","value":4', calls[0][0][1]["content"])
            self.assertIn("current_bonus.value", calls[0][0][0]["content"])
            self.assertEqual(state.view()["messages"][-1]["text"], "先保留金币")
            self.assertEqual(state.view()["settings"]["display_mode"], "outside")
            self.assertTrue(state.view()["prompt_used"])
            state.update_snapshot("run-1", {"phase": "shop", "money": 5}, "zh_CN")
            self.assertTrue(state.view()["prompt_used"])
            self.assertEqual(state.view()["scene_id"], shop_scene)
            state.update_snapshot("run-1", {"phase": "blind_select"}, "zh_CN")
            self.assertFalse(state.view()["prompt_used"])
            self.assertGreater(state.view()["scene_id"], shop_scene)
            state.update_snapshot("run-2", {"phase": "other"}, "en-us")
            self.assertEqual(state.view()["messages"], [])
            self.assertEqual(bridge.SessionState(settings_path=Path(temp) / "settings.json").view()["settings"]["model"], "gpt-6-luna")

    def test_invalid_choice_and_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json", clock=lambda: 10)
            state.update_snapshot("run-1", {"phase": "shop"}, "zh_CN")
            with self.assertRaises(ValueError):
                state.update_settings({"model": "unsupported"})
            state.clock = lambda: 16
            with self.assertRaisesRegex(RuntimeError, "stale_state"):
                state.ask("怎么买？", lambda *_: "不应调用")

    def test_runner_crash_does_not_leave_session_busy(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {"phase": "shop"}, "zh_CN")

            def crash(*_):
                raise ValueError("private detail")

            with self.assertRaisesRegex(RuntimeError, "cli_failed"):
                state.ask("买吗？", crash)
            self.assertFalse(state.view()["pending"])

    def test_request_and_rejections(self):
        seen = []
        server = HTTPServer((bridge.HOST, 0), bridge.make_handler(lambda messages: seen.append(messages) or "先看经济"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://{bridge.HOST}:{server.server_port}"

        def post(body, headers=None):
            request = Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                              headers=headers or {"Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=2) as response:
                    return response.status, json.load(response)
            except HTTPError as exc:
                return exc.code, json.load(exc)

        try:
            with urlopen(base + "/health", timeout=2) as response:
                self.assertEqual(json.load(response)["reasoning_effort"], "high")
            payload = {"model": "gpt-6-sol", "stream": False,
                       "messages": [{"role": "user", "content": "怎么买？"}]}
            status, answer = post(payload)
            self.assertEqual(status, 200)
            self.assertEqual(answer["choices"][0]["message"]["content"], "先看经济")
            self.assertEqual(seen, [payload["messages"]])
            status, answer = post({**payload, "model": "other"})
            self.assertEqual(status, 400)
            self.assertEqual(len(seen), 1)
            status, answer = post({**payload, "messages": [{"role": "tool", "content": "execute"}]})
            self.assertEqual(status, 400)
            status, answer = post(payload, {"Content-Type": "text/plain"})
            self.assertEqual(status, 403)
            status, answer = post(payload, {"Content-Type": "application/json", "Origin": "https://example.com"})
            self.assertEqual(status, 403)
            self.assertEqual(len(seen), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_cli_uses_selected_model_read_only_and_without_api_key(self):
        captured = {}

        def fake_run(command, **options):
            captured["command"] = command
            captured["options"] = options
            Path(command[command.index("-o") + 1]).write_text("建议保留金币\n", encoding="utf-8")
            return type("Result", (), {"returncode": 0})()

        with patch.object(bridge.subprocess, "run", side_effect=fake_run), patch.dict(
            bridge.os.environ, {"OPENAI_API_KEY": "dummy", "CODEX_API_KEY": "dummy"}
        ):
            answer = bridge.run_codex([{"role": "user", "content": "怎么买？"}],
                                      model="gpt-6-luna", effort="medium", executable="/bin/true")
        self.assertEqual(answer, "建议保留金币")
        command = captured["command"]
        self.assertEqual(command[command.index("-m") + 1], "gpt-6-luna")
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertIn("model_reasoning_effort=medium", command)
        self.assertIn("--ephemeral", command)
        self.assertNotIn("OPENAI_API_KEY", captured["options"]["env"])
        self.assertNotIn("CODEX_API_KEY", captured["options"]["env"])




PLAIN_VALUES = {"t_mult": 0, "h_mult": 0, "mult": 0, "h_dollars": 0, "x_mult": 1, "t_chips": 0,
                "bonus": 0, "perma_bonus": 0, "d_size": 0, "h_size": 0}


def plain_card(rank, suit, name, remaining=True):
    return {"name": name, "rank": rank, "suit": suit, "key": "c_base", "set": "Default",
            "sell_cost": 1, "values": dict(PLAIN_VALUES), "remaining_unplayed": remaining}


class CompactStateTest(unittest.TestCase):
    """2026-11-04：整副牌目录占局面 56%–68%，几乎全是默认值；压缩只去默认值，不丢信息。"""

    def test_deck_catalog_groups_plain_cards_and_keeps_every_non_default_field(self):
        foil = dict(plain_card("6", "Clubs", "6♣"), edition="foil", seal="Purple")
        hiker = plain_card("King", "Hearts", "K♥", remaining=False)
        hiker["values"]["perma_bonus"] = 10
        lucky = dict(plain_card("7", "Hearts", "Lucky Card"), key="m_lucky", set="Enhanced")
        catalog = [plain_card("Ace", "Spades", "A♠"), plain_card("10", "Diamonds", "10♦", remaining=False),
                   foil, hiker, lucky]
        compact = bridge.compact_deck_catalog(catalog)
        self.assertEqual(compact["draw_pile"], "A♠")
        self.assertEqual(compact["not_in_draw_pile"], "10♦")
        self.assertEqual(compact["modified"], [
            {"name": "6♣", "edition": "foil", "seal": "Purple", "in_draw_pile": True},
            {"name": "K♥", "values": {"perma_bonus": 10}, "in_draw_pile": False},
            # 增强牌名字里没有点数花色，点数花色必须留着。
            {"name": "Lucky Card", "rank": "7", "suit": "Hearts", "key": "m_lucky", "set": "Enhanced",
             "in_draw_pile": True}])
        self.assertEqual(catalog[0]["values"]["x_mult"], 1)  # 不改原快照

    def test_state_message_is_compact_and_cli_prompt_is_not_double_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            hand = [dict(plain_card("Ace", "Spades", "A♠"), position=1, description="+11 chips")]
            hand[0].pop("remaining_unplayed")
            state.update_snapshot("r1", {"phase": "play", "snapshot_revision": 1, "money": 4,
                                         "hand": hand, "deck_catalog": [plain_card("2", "Clubs", "2♣")],
                                         "hands_left": 4, "discards_left": 3}, "en-us")
            captured = []
            state.ask("What should I play?", lambda prompt, *_: captured.append(prompt) or "ok")
            content = captured[0][-2]["content"]
            self.assertNotIn('", "', content)  # 紧凑分隔符
            context = json.loads(content.removeprefix("Latest visible state JSON: "))
            self.assertEqual(context["snapshot"]["hand"],
                             [{"name": "A♠", "position": 1, "description": "+11 chips"}])
            self.assertEqual(context["snapshot"]["deck_catalog"]["draw_pile"], "2♣")
            self.assertEqual(state.snapshot["hand"][0]["values"]["x_mult"], 1)  # 依据仍按原快照算
            self.assertIn("draw_pile", captured[0][0]["content"])
        seen = {}

        def fake_run(command, **options):
            seen["input"] = options["input"]
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        with patch.object(bridge.subprocess, "run", side_effect=fake_run):
            bridge.run_claude(captured[0], executable=sys.executable)
        self.assertIn(content, seen["input"])  # 局面 JSON 原样进入，不再套一层 JSON 把引号全转义
        self.assertNotIn('\\"', seen["input"])


class SettingsMenu(unittest.TestCase):
    def test_面板只列出两个_Claude_模型并带短显示名(self):
        caps = bridge.capabilities()
        self.assertEqual([m["id"] for m in caps["models"]], ["claude-opus-5-5", "claude-fable-5-1"])
        self.assertEqual([m["name"] for m in caps["models"]], ["Opus 5.5", "Fable 5.1"])
        for m in caps["models"]:
            self.assertEqual(m["efforts"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(caps["goals"], [{"id": "clear", "enabled": True}, {"id": "endless", "enabled": False}])

    def test_无尽冲分目前不可选_极高与最大强度可选(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            with self.assertRaises(ValueError):
                state.update_settings({"play_goal": "endless"})
            state.update_settings({"model": "claude-fable-5-1", "effort": "max"})
            self.assertEqual(state.view()["settings"]["effort"], "max")
            state.update_settings({"effort": "xhigh"})
            self.assertEqual(state.view()["settings"]["effort"], "xhigh")

if __name__ == "__main__":
    unittest.main()
