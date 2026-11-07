# Cardwisp for Balatro

**English** · [中文](#小丑牌灵cardwisp-for-balatro)

Cardwisp is an AI advisor that lives inside Balatro. Open the panel during a run, ask a question (or send the suggested one), and get short advice based on what is currently on screen. **It only reads the visible game state and gives text advice. It never plays cards, buys items, or takes any action for you.**

## Features

- **In-game chat panel.** Click **Cardwisp** in the top-right corner or press **F8** (Fn + F8 on a Mac keyboard). Drag the left edge to resize it.
- **Scene-aware questions.** The shop, booster packs, playing a hand, and blind selection each get a suggested question. Send it as is or type your own.
- **Checked numbers instead of guesses.** Before asking the model, Cardwisp works out the facts it can verify. In the shop that is costs, the balance left after buying, interest tiers, Joker slots, and sell-then-buy swaps. When playing a hand it is the score still needed, hands and discards left, and **exact final scores for the hands that can be verified**.
- **Follows the game language.** The interface is available in English and Simplified Chinese; other languages fall back to English. Card names and effects are read in the game's own language.
- **Optional companion window on macOS.** Advice can be shown in a separate window docked next to the game instead of inside it.

## Requirements

- **Balatro for PC/Mac (Steam).** Mobile, console and Apple Arcade versions cannot load mods.
- **[Lovely](https://github.com/ethangreen-dev/lovely-injector)** and **[Steamodded](https://github.com/Steamodded/smods)** 1.0.0~BETA-0301a or newer.
- **Python 3.9 or newer**, to run the local bridge.
- **[Claude Code](https://claude.com/claude-code)** installed and signed in. Run `claude` once in a terminal to log in. Cardwisp uses your own Claude account: it works with a Claude subscription or with an `ANTHROPIC_API_KEY`, and each question counts toward that account's usage.
- For the macOS companion window: Xcode Command Line Tools (`swiftc`). It is compiled on first use.

Cardwisp is developed and tested on macOS. The in-game panel and the bridge are plain Lua and Python and should work on Windows too, but Windows has not been tested yet.

## Install

1. Download and unzip this folder anywhere.
2. Install the mod into your Balatro `Mods` folder:

   ```sh
   python3 scripts/install.py --mods-dir "<your Balatro Mods folder>"
   ```

   The `Mods` folder is usually `~/Library/Application Support/Balatro/Mods` on macOS and `%AppData%\Balatro\Mods` on Windows. The script copies only the mod's own files. If an older version exists, it is backed up to `assistant-backups/` next to the `Mods` folder first. It never touches other mods, the game itself, or your saves.

   You can also copy `main.lua`, `balatro-assistant.json`, `modules/`, `locales/` and `LICENSE` into `Mods/balatro-assistant/` by hand.

3. Start the bridge and keep its window open while you play:

   ```sh
   python3 scripts/cli_bridge.py
   ```

   On macOS you can double-click `scripts/start_bridge.command` instead.

4. Start the game with mods enabled. **On macOS, launch it with `run_lovely_macos.sh` in the game folder.** The Steam Play button does not load Lovely there. On Windows, Lovely loads when you start the game from Steam as usual.

To uninstall, delete `Mods/balatro-assistant/`.

## Usage

- Open or close the panel with the **Cardwisp** button or **F8**. Press Enter to send and Esc to leave the input box. Chinese and other IME input is supported; finish composing before pressing Enter.
- The settings icon in the panel picks the model (Opus 5.5 or Fable 5.1), the thinking effort, and whether advice shows inside the game or in the companion window. Settings take effect from the next question.
- If the game state changes while the model is answering, the answer is discarded and you are asked to try again, so you never get advice for a state that no longer exists.
- Chat history lives in the bridge's memory and is cleared when a new run starts or the bridge stops.

## Privacy and cost

- The game syncs the visible state to the bridge on your own computer (`127.0.0.1:8765`) about once a second. **Nothing is sent to a model until you ask a question.**
- Each question sends the visible state, the bookkeeping above, your question and up to eight recent chat messages to Anthropic through your Claude Code CLI. No other data is collected.
- Hidden information stays hidden: face-down cards, unopened packs and the draw order are never read.
- Cardwisp does not store or ask for API keys. `model.example.json` shows an optional advanced setup for connecting another compatible model server directly. That path skips the bridge's checks and bookkeeping.

## Limitations

- Advice comes from a language model and can be wrong. Treat it as a second opinion.
- Exact scores are only listed when every effect involved can be verified. They are left out when face-down cards are in hand, for Bosses that change scoring (such as The Flint), and for some Jokers. An unlisted play is not necessarily worse.
- Some dynamic card text that cannot be resolved from the visible state is shown as `?`, and the model is told the value is unknown.
- Built for mouse and keyboard on desktop. Controllers and touch screens are not supported.

## Development

```sh
python3 tests/run_all.py
```

The Lua tests use the LuaJIT library bundled with Steam Balatro on macOS. Set `BALATRO_LUA_LIBRARY` to point at another Lua 5.1/LuaJIT library. The tests never start or change a run.

Layout:
- `modules/core.lua`: reads the game state.
- `modules/panel.lua`: in-game panel.
- `modules/model.lua`: talks to the bridge.
- `scripts/cli_bridge.py`: shared session, prompts and the Claude CLI.
- `scripts/shop_decision.py`, `scripts/scene_decision.py` and `scripts/play_scores.py` with `scripts/hand_score.py`: the checked bookkeeping and the scorer.
- `scripts/CardwispCompanion.swift` and `companion/index.html`: the macOS window.

Design notes and known issues are in `docs/` (in Chinese).

## License

Released under the [MIT License](LICENSE). The license covers Cardwisp's own code and documents only. Balatro, Steamodded, Lovely and other mods are not covered, and Cardwisp contains no game assets. Cardwisp is a fan-made mod and is not affiliated with or endorsed by LocalThunk or Playstack.

---

# 小丑牌灵（Cardwisp for Balatro）

[English](#cardwisp-for-balatro) · **中文**

小丑牌灵是装在 Balatro 里的 AI 顾问。牌局中打开面板，提个问题（或直接发送预填的问题），就能根据当前屏幕上的局面得到简短建议。**它只读取可见局面、给出文字建议，绝不替你出牌、买东西或执行任何操作。**

## 功能

- **游戏内聊天面板。** 点右上角「牌灵」或按 **F8**（Mac 键盘为 Fn + F8）打开。拖动面板左边缘可以调宽度。
- **按场景预填问题。** 商店、开卡包、出牌、选盲注各有预填问题，可以直接发送，也可以自己改写。
- **核对过的数字，不靠模型猜。** 提问前，牌灵会先算好能确定的事实：商店里是价格、买完剩多少钱、利息档位、小丑格子、卖旧买新的账目；出牌时是还差多少分、剩几手几弃，以及**能确定的出牌组合的精确最终得分**。
- **跟随游戏语言。** 界面有简体中文和英语，其他语言回退英语；卡牌名称和效果按游戏自己的语言读取。
- **macOS 可选独立窗口。** 建议可以显示在停靠游戏旁边的独立窗口里，而不是游戏画面内。

## 运行要求

- **电脑版 Balatro（Steam）。** 手机版、主机版和 Apple Arcade 版都不能装模组。
- **[Lovely](https://github.com/ethangreen-dev/lovely-injector)** 和 **[Steamodded](https://github.com/Steamodded/smods)** 1.0.0~BETA-0301a 或更新版本。
- **Python 3.9 或更新版本**，用于运行本机桥接程序。
- **已安装并登录 [Claude Code](https://claude.com/claude-code)**：在终端运行一次 `claude` 完成登录。牌灵使用你自己的 Claude 账号，Claude 订阅或 `ANTHROPIC_API_KEY` 都可以，每次提问计入该账号的用量。
- 使用 macOS 独立窗口需要 Xcode 命令行工具（`swiftc`），首次使用时自动编译。

牌灵在 macOS 上开发和测试。游戏内面板和桥接程序都是普通的 Lua 与 Python，理论上也能在 Windows 上运行，但还没在 Windows 上测试过。

## 安装

1. 下载并把这个文件夹解压到任意位置。
2. 把模组装进 Balatro 的 `Mods` 文件夹：

   ```sh
   python3 scripts/install.py --mods-dir "<你的 Balatro Mods 文件夹>"
   ```

   `Mods` 文件夹通常在：macOS 是 `~/Library/Application Support/Balatro/Mods`，Windows 是 `%AppData%\Balatro\Mods`。脚本只复制本模组自己的文件；已有旧版本时，先备份到 `Mods` 旁边的 `assistant-backups/`。它不会改动其他模组、游戏本身和存档。

   也可以手动把 `main.lua`、`balatro-assistant.json`、`modules/`、`locales/` 和 `LICENSE` 复制到 `Mods/balatro-assistant/`。

3. 启动桥接程序，玩的时候保持它的窗口开着：

   ```sh
   python3 scripts/cli_bridge.py
   ```

   macOS 上也可以直接双击 `scripts/start_bridge.command`。

4. 以启用模组的方式启动游戏。**macOS 上请用游戏目录里的 `run_lovely_macos.sh` 启动**，Steam 的「开始游戏」按钮不会加载 Lovely。Windows 上照常从 Steam 启动即可，Lovely 会自动生效。

卸载：删除 `Mods/balatro-assistant/`。

## 使用

- 用「牌灵」按钮或 **F8** 打开、收起面板。Enter 发送，Esc 离开输入框。支持中文等输入法，选完词再按 Enter。
- 面板里的设置图标可以选择模型（Opus 5.5 或 Fable 5.1）、思考强度，以及在游戏内还是独立窗口显示。设置从下一次提问起生效。
- 模型回答期间局面一旦变化，旧回答会被丢弃并提示重新提问，不会拿过时的局面给你建议。
- 聊天记录只保存在桥接程序的内存里，开新局或关闭桥接程序后清空。

## 隐私与费用

- 游戏每秒把可见局面同步给**你自己电脑上**的桥接程序（`127.0.0.1:8765`）。**你不提问，就不会有任何内容发给模型。**
- 每次提问会把可见局面、上面那些核对数据、你的问题和最多八条近期对话，通过你的 Claude Code 命令行发给 Anthropic。除此之外不收集任何数据。
- 隐藏信息不会被读取：背面朝下的牌、没打开的卡包和抽牌顺序都看不到。
- 牌灵不保存也不索要 API 密钥。`model.example.json` 是可选的进阶配置示例，用来直连其他兼容的模型服务；这条路径不经过桥接程序的核对数据。

## 已知限制

- 建议来自语言模型，可能出错，请当作参考意见。
- 只有涉及的每个效果都能确认时，才会列出精确得分。手里有背面朝下的牌、遇到会改变计分的 Boss（如燧石）、或者有部分小丑在场时，不会列出得分。没列出的出牌不代表分数更低。
- 少数卡面动态数值无法从可见局面确定时，会显示为 `?`，模型也会被告知该数值未知。
- 为桌面键鼠设计，不支持手柄和触屏。

## 开发

```sh
python3 tests/run_all.py
```

Lua 测试在 macOS 上使用 Steam 版 Balatro 自带的 LuaJIT 库；其他位置可用 `BALATRO_LUA_LIBRARY` 指定兼容 Lua 5.1/LuaJIT 的库。测试不会启动或改动牌局。

代码结构：
- `modules/core.lua`：读取局面。
- `modules/panel.lua`：游戏内面板。
- `modules/model.lua`：与桥接程序通信。
- `scripts/cli_bridge.py`：共享会话、提示词和 Claude 命令行调用。
- `scripts/shop_decision.py`、`scripts/scene_decision.py`，以及 `scripts/play_scores.py` 配合 `scripts/hand_score.py`：核对数据和计分器。
- `scripts/CardwispCompanion.swift` 与 `companion/index.html`：macOS 独立窗口。

设计说明与已知问题见 `docs/`。

## 许可证

以 [MIT 许可证](LICENSE)发布。许可证只覆盖牌灵自己的代码与文档；Balatro 游戏本身、Steamodded、Lovely 及其他模组不在此列，牌灵也不包含任何游戏资源。牌灵是玩家自制模组，与 LocalThunk、Playstack 没有关联，也未获其认可。
