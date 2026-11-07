# -*- coding: utf-8 -*-
"""面板回答整形：只取标记后的最终答案、剥掉 Markdown、提示词写明三段短格式。

人机实测 27 条回答：中位 770 字、26 条带 Markdown 标题，两条把模型的英文推演整段漏进正文；
游戏内面板与外部窗口都是纯文本绘制，符号原样显示。
"""

import importlib.util
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/cli_bridge.py"
spec = importlib.util.spec_from_file_location("cli_bridge", path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class TidyAnswer(unittest.TestCase):
    def test_只保留答案标记之后的文字(self):
        raw = "Let me think. Options: A or B. Hmm.\n" * 5 + "[[ANSWER]]\n建议：买火箭，离店。\n理由：便宜。"
        self.assertEqual(bridge.tidy_answer(raw), "建议：买火箭，离店。\n理由：便宜。")

    def test_没有标记时长推演后的第一个标题当作答案起点(self):
        raw = "x" * 400 + "\n## 建议：先弃 A♣\n- 理由一\n"
        self.assertEqual(bridge.tidy_answer(raw), "建议：先弃 A♣\n· 理由一")

    def test_短前言不会被当成推演丢掉(self):
        raw = "你说得对。\n## 结论\n买。"
        self.assertEqual(bridge.tidy_answer(raw), "你说得对。\n结论\n买。")

    def test_剥掉标题粗体与列表符号(self):
        raw = "## 结论\n**买 X**，不买 Y。\n- 理由一\n* 理由二\n1. 第三\n\n\n\n### 注意\n__风险__"
        self.assertEqual(bridge.tidy_answer(raw), "结论\n买 X，不买 Y。\n· 理由一\n· 理由二\n1. 第三\n\n注意\n风险")

    def test_干净文字原样(self):
        self.assertEqual(bridge.tidy_answer("建议：打 K K Q Q。\n理由：11 级两对。"), "建议：打 K K Q Q。\n理由：11 级两对。")

    def test_空答案保持为空(self):
        self.assertEqual(bridge.tidy_answer("   "), "")


class AskUsesFormat(unittest.TestCase):
    def test_提示词写明三段短格式_回答入库前已整形(self):
        with tempfile.TemporaryDirectory() as temp:
            state = bridge.SessionState(settings_path=Path(temp) / "settings.json")
            state.update_snapshot("r1", {"phase": "shop", "ante": 2, "shop": []}, "zh_CN")
            prompts = []
            answer = state.ask("这个商店怎么选？", lambda prompt, *_: prompts.append(prompt) or
                               "thinking thinking\n[[ANSWER]]\n## 建议\n**买火箭**")
            system = prompts[-1][0]["content"]
            self.assertIn("[[ANSWER]]", system)
            self.assertIn("300", system)
            for label in ("结论：", "理由：", "注意："):
                self.assertIn(label, system)
            self.assertEqual(answer, "建议\n买火箭")
            self.assertEqual(state.view()["messages"][-1]["text"], "建议\n买火箭")


if __name__ == "__main__":
    unittest.main()
