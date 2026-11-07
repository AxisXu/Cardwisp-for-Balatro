"""只在公开信息足以确定时计算一手牌的得分；其余情况返回未知。

依据本机游戏源码：最终得分为 math.floor(筹码 × 倍率)。只有组成牌型的牌参与计分，
垫牌不计分；打出的牌按顺序逐张结算，每张牌上按小丑从左到右触发「计分时」效果，
随后 Joker Effects 阶段再按同一顺序加算、乘算。成长型小丑在 context.before 阶段
先更新再参与计分，因此这里复现更新后的值，而不是卡面显示值。

这不是完整计分器。只收录已逐项核对游戏源码、且不含随机或隐藏状态的小丑；遇到未收录
的小丑效果、带版本修饰的小丑、被禁用的小丑或牌、带强化或蜡封的牌、无法判定的牌型、
以及无法精确复现的成长乘算，一律返回 None，不猜测。覆盖率用真实对局的公开结算回放
校验：算得出来的必须与游戏实际得分完全一致。

2026-11-07 自 experiments/cardwisp_eval/hand_score.py 移植进插件（实验里 22/22 可核对手全对）。
插件版只改两处，都是为了不依赖游戏语言：Boss 先按 key 认（名字和效果文字随语言变化），
成长小丑的当前值先取插件的结构化 current_bonus，取不到再读英文卡面文字。
"""

import re

from plain_hand_type import classify_plain_hand


BASE_CHIPS = {str(value): value for value in range(2, 10)}
BASE_CHIPS.update(T=10, J=10, Q=10, K=10, A=11)
FACE_RANKS = ("J", "Q", "K")
FLUSH_TYPES = ("Flush", "Straight Flush", "Flush House", "Flush Five")
CURRENT_X_MULT = re.compile(r"\(Currently X([0-9]+(?:\.[0-9]+)?) Mult\)")
CURRENT_ADD_MULT = re.compile(r"\(Currently \+([0-9]+(?:\.[0-9]+)?) Mult\)")
CURRENT_ADD_CHIPS = re.compile(r"\(Currently \+?([0-9]+(?:\.[0-9]+)?) Chips\)")
CURRENT_PLAIN_ADD = re.compile(r"\(Currently \+([0-9]+(?:\.[0-9]+)?)\)")
# 衰减型小丑的当前值就写在卡面开头：冰淇淋 "+100 Chips …"、爆米花 "+20 Mult …"。
# 卡面文本取自游戏真实 UI 描述，随衰减变化；衰减发生在本手结算之后，因此显示值适用本手。
LEADING_ADD_CHIPS = re.compile(r"^\+([0-9]+) Chips")
LEADING_ADD_MULT = re.compile(r"^\+([0-9]+) Mult")
# 拉面卡面给两位小数（X1.01、X1.05），0.01 步长可精确还原，不需要区间。
LEADING_X_MULT = re.compile(r"^X([0-9]+(?:\.[0-9]+)?) Mult")
LOYALTY_REMAINING = re.compile(r"([0-9]+) remaining")
# 插件 current_bonus.kind 与卡面文字模式的对应：结构化数值不随游戏语言变化。
CURRENT_BONUS_KINDS = {CURRENT_X_MULT: "x_mult", LEADING_X_MULT: "x_mult",
                       CURRENT_ADD_MULT: "add_mult", LEADING_ADD_MULT: "add_mult",
                       CURRENT_PLAIN_ADD: "add_mult",
                       CURRENT_ADD_CHIPS: "chips", LEADING_ADD_CHIPS: "chips"}
IDOL_TARGET = re.compile(r"Each played (\w+) of (Spade|Heart|Club|Diamond)s?")
IDOL_RANKS = {"Ace": "A", "King": "K", "Queen": "Q", "Jack": "J", "10": "T"}
SUIT_WORDS = {"Spade": "S", "Heart": "H", "Club": "C", "Diamond": "D"}
SAME_COLOR = {"S": ("S", "C"), "C": ("S", "C"), "H": ("H", "D"), "D": ("H", "D")}


def _is_suit(card, suit, context):
    """card.lua 的 is_suit：涂抹小丑在场时同色花色互相算作对方。"""
    actual = (card.get("value") or {}).get("suit")
    if actual == suit:
        return True
    return bool(context.get("smeared")) and actual in SAME_COLOR.get(suit, ())
EFFECT_SUIT = re.compile(r"\b(Spade|Heart|Club|Diamond) suit\b")
EVEN_RANKS = ("T", "8", "6", "4", "2")
OBELISK_STEP = 0.2  # 游戏 game.lua 中 j_obelisk 的 config.extra


# 逐个核对游戏 localization 里全部 30 个盲注后，只有这四个会改变单手计分的数学：
# The Flint 把基础筹码与倍率减半；The Arm 降低所打牌型等级；
# Crimson Heart 每手随机禁用一张小丑（随机，不可知）；
# Amber Acorn 打乱小丑顺序，而顺序直接决定加算与乘算的先后。
SCORING_ALTERING_BLIND_KEYS = {"bl_flint", "bl_arm", "bl_final_heart", "bl_final_acorn"}
FORCED_DISCARD_BLIND_KEYS = {"bl_hook": 2}
HAND_RULE_BLIND_NAMES = {"bl_psychic": "The Psychic", "bl_eye": "The Eye", "bl_mouth": "The Mouth"}
SCORING_ALTERING_BLIND_EFFECTS = (
    "base chips and", "mult are halved", "decrease level of played",
    "random joker disabled", "flips and shuffles all joker",
)


# 每打出一手就强制弃掉若干张的 Boss（如 The Hook）。那些弃牌会触发
# 「按弃牌成长/衰减」的小丑，而它发生在本手计分之前还是之后，公开信息看不出来。
FORCED_DISCARD_EFFECT = re.compile(
    r"discards?\s+(\d+)\s+random cards? per hand played", re.IGNORECASE)


def forced_discards_per_hand(blinds):
    """当前 Boss 每打出一手会强制弃掉几张；没有就返回 0。"""
    for blind in (blinds or {}).values():
        if not isinstance(blind, dict) or blind.get("status") != "CURRENT":
            continue
        if blind.get("disabled") is True:
            continue
        if blind.get("key"):
            if blind["key"] in FORCED_DISCARD_BLIND_KEYS:
                return FORCED_DISCARD_BLIND_KEYS[blind["key"]]
            continue
        found = FORCED_DISCARD_EFFECT.search(str(blind.get("effect", "")))
        if found:
            return int(found.group(1))
    return 0


# 本回合只能打一种牌型：第一手之后，牌型不符的那几手直接结算 0 分。
# 锁定的是哪一种只能从本回合历史得知，计分器拿不到，因此只能拒绝给数。
SINGLE_HAND_TYPE_EFFECT = "play only 1 hand type"


def blinds_alter_scoring(blinds, round_state=None):
    """当前盲注是否会改变单手计分的数学。"""
    played = (round_state or {}).get("hands_played")
    for blind in (blinds or {}).values():
        if not isinstance(blind, dict) or blind.get("status") != "CURRENT":
            continue
        if blind.get("disabled") is True:
            continue
        if blind.get("key"):
            if blind["key"] in SCORING_ALTERING_BLIND_KEYS:
                return True
            continue
        effect = str(blind.get("effect", "")).lower()
        if any(mark in effect for mark in SCORING_ALTERING_BLIND_EFFECTS):
            return True
    return False


class _Unknown(Exception):
    """公开信息不足以确定得分。"""


def _current_value(joker, pattern, label):
    bonus = joker.get("current_bonus")
    if isinstance(bonus, dict) and bonus.get("kind") == CURRENT_BONUS_KINDS.get(pattern) and \
            type(bonus.get("value")) in (int, float):
        return float(bonus["value"])
    effect = (joker.get("value") or {}).get("effect") or ""
    found = pattern.search(effect)
    if not found:
        raise _Unknown("%s 的卡面没有公开当前数值" % label)
    return float(found.group(1))


def _suit_mult(suit, bonus):
    def apply(card, totals, context):
        if _is_suit(card, suit, context):
            totals["mult"] += bonus
    return apply


def _numeric(value):
    return value if type(value) in (int, float) else 0


def _card_is_debuffed(card):
    return bool((card.get("state") or {}).get("debuff")) if isinstance(card, dict) else False


def _is_stone(card):
    return (str(((card or {}).get("modifier") or {}).get("enhancement") or "").upper()
            == "STONE")


def _is_face(card, context):
    """丑脸小丑让所有牌都算人头牌；card.lua:964 的 is_face 对被禁用的牌返回空。

    石头牌没有正常的点数身份（card.lua:957-969），因此也不是人头牌。
    """
    if _card_is_debuffed(card) or _is_stone(card):
        return False
    if context.get("all_cards_are_face"):
        return True
    return card["value"]["rank"] in FACE_RANKS


def _first_face_x_mult(factor):
    """card.lua 只比较「当前牌是否就是计分集合里第一张人头牌」，没有用过即失效的标记：
    因此重触发时会再次乘算；而若那张牌被 Boss 禁用，计分循环跳过它，它就一次也不触发。"""
    def apply(card, totals, context):
        if card is context["first_face"]:
            totals["mult"] *= factor
    return apply


def _contains_chips(hand_type, bonus):
    """对应游戏 t_chips：打出的牌「包含」该牌型分组即触发，不要求最终牌型相等。"""
    def apply(totals, context):
        if hand_type in context["contains"]:
            totals["chips"] += bonus
    return apply


def _contains_mult(hand_type, bonus):
    def apply(totals, context):
        if hand_type in context["contains"]:
            totals["mult"] += bonus
    return apply


def _rank_chips_and_mult(ranks, chips, mult):
    def apply(card, totals, _context):
        if card["value"]["rank"] in ranks:
            totals["chips"] += chips
            totals["mult"] += mult
    return apply


def _rank_x_mult_by_effect_suit(factor, label):
    """轮换花色乘算：当前花色写在卡面上，未来回合的花色未知，不推断。"""
    def apply(card, totals, context):
        effect = (context["joker"].get("value") or {}).get("effect") or ""
        found = EFFECT_SUIT.search(effect)
        if not found:
            raise _Unknown("%s 的卡面没有公开当前花色" % label)
        if _is_suit(card, SUIT_WORDS[found.group(1)], context):
            totals["mult"] *= factor
    return apply


ODD_RANKS = ("A", "9", "7", "5", "3")
# 举起的拳头按点数本身取值；A 在游戏里的 nominal 为 11。
RANK_VALUES = {str(v): v for v in range(2, 10)}
RANK_VALUES.update(T=10, J=10, Q=10, K=10, A=11)
# card.lua 的 base.id：T/J/Q/K 各不相同，选「最小的一张」必须按它。
RANK_ORDER_IDS = {str(v): v for v in range(2, 10)}
RANK_ORDER_IDS.update(T=10, J=11, Q=12, K=13, A=14)


def _rank_chips(ranks, bonus):
    def apply(card, totals, _context):
        if card["value"]["rank"] in ranks:
            totals["chips"] += bonus
    return apply


def _face_chips(bonus):
    def apply(card, totals, context):
        if _is_face(card, context):
            totals["chips"] += bonus
    return apply


def _face_mult(bonus):
    def apply(card, totals, context):
        if _is_face(card, context):
            totals["mult"] += bonus
    return apply


def _suit_chips(suit, bonus):
    def apply(card, totals, context):
        if _is_suit(card, suit, context):
            totals["chips"] += bonus
    return apply


def _flat_chips(bonus):
    def apply(totals, _context):
        totals["chips"] += bonus
    return apply


def _bounded_fixed_x_mult(low, high):
    """条件依赖公开局面没给的数据（如整副牌的强化牌数）时，给 [不触发, 触发] 的区间。"""
    def apply(totals, context):
        totals["bounded"] = True
        totals["mult"] *= high if context["bound"] == "high" else low
    return apply


def _fixed_x_mult(factor):
    def apply(totals, _context):
        totals["mult"] *= factor
    return apply


def _contains_x_mult(hand_type, factor):
    def apply(totals, context):
        if hand_type in context["contains"]:
            totals["mult"] *= factor
    return apply


def _all_suits_x_mult(factor):
    """花盆：计分牌里四个花色齐全才生效。"""
    def apply(totals, context):
        suits = {s for card in context["scoring"] for s in "SHCD" if _is_suit(card, s, context)}
        if len(suits) == 4:
            totals["mult"] *= factor
    return apply


def _club_and_other_x_mult(factor):
    """重影：计分牌里既有梅花又有非梅花。"""
    def apply(totals, context):
        suits = {s for card in context["scoring"] for s in "SHCD" if _is_suit(card, s, context)}
        if "C" in suits and len(suits) > 1:
            totals["mult"] *= factor
    return apply


def _x_mult_on_final_hand(factor):
    """杂技演员：本轮最后一手才生效；剩余手数未知时给区间。"""
    def apply(totals, context):
        left = (context["round_state"] or {}).get("hands_left")
        if type(left) is int:
            if left == 1:
                totals["mult"] *= factor
            return
        totals["bounded"] = True
        if context["bound"] == "high":
            totals["mult"] *= factor
    return apply


def _money_is_stable(context):
    """本手计分过程中会不会有现金进账。

    card.lua:3936 的公牛与 4046 的吊靴带读的是 `dollars + dollar_buffer`，
    而缓冲来自计分牌当场付的钱（card.lua:1085 的 p_dollars，例如金蜡封的 $3）。
    有这类牌时，出牌前的现金不等于结算时的现金。
    """
    for card in context["scoring"]:
        modifier = card.get("modifier") or {}
        if str(modifier.get("seal") or "").upper() == "GOLD":
            raise _Unknown("计分牌带金蜡封，会在结算中改变现金，按现金计分的小丑无法确定")
        if str(modifier.get("enhancement") or "").upper() == "LUCKY":
            raise _Unknown("计分牌是幸运牌，可能在结算中产钱，按现金计分的小丑无法确定")
    if any(joker.get("key") == "j_rough_gem" for joker in context["jokers"]):
        raise _Unknown("粗糙宝石会在结算中产钱，按现金计分的小丑无法确定")


def _chips_per_dollar(bonus):
    def apply(totals, context):
        money = (context["round_state"] or {}).get("money")
        if type(money) not in (int, float):
            raise _Unknown("需要当前金钱数，局面未提供")
        _money_is_stable(context)
        totals["chips"] += bonus * max(0, int(money))
    return apply


def _mult_per_dollars(bonus, per):
    def apply(totals, context):
        _money_is_stable(context)
        money = (context["round_state"] or {}).get("money")
        if type(money) not in (int, float):
            raise _Unknown("需要当前金钱数，局面未提供")
        totals["mult"] += bonus * (max(0, int(money)) // per)
    return apply


def _mult_from_other_sell_values():
    """海盗：把其余小丑的出售价加进倍率；出售价是公开字段。"""
    def apply(totals, context):
        total = 0
        for other in context["jokers"]:
            if other is context["joker"]:
                continue
            sell = (other.get("cost") or {}).get("sell")
            if type(sell) not in (int, float):
                raise _Unknown("有小丑的出售价未提供，海盗收益无法确定")
            total += int(sell)
        totals["mult"] += total
    return apply


def _rank_x_mult(ranks, factor):
    def apply(card, totals, _context):
        if card["value"]["rank"] in ranks:
            totals["mult"] *= factor
    return apply


def _idol_x_mult(factor):
    """偶像：当前生效的点数与花色写在卡面上，每回合变化；未来的组合未知。"""
    def apply(card, totals, context):
        effect = (context["joker"].get("value") or {}).get("effect") or ""
        found = IDOL_TARGET.search(effect)
        if not found:
            raise _Unknown("偶像的卡面没有公开当前点数与花色")
        rank, suit_word = found.group(1), found.group(2)
        if (card["value"]["rank"] == IDOL_RANKS.get(rank, rank)
                and _is_suit(card, SUIT_WORDS[suit_word], context)):
            totals["mult"] *= factor
    return apply


def _held_x_mult_per_rank(rank, factor):
    """留在手里的某点数牌各乘一次；哑剧让手牌效果再触发一次。"""
    def apply(totals, context):
        held = context["held_cards"]
        if held is None:
            raise _Unknown("需要出牌后仍留在手里的牌，局面未提供")
        times = 2 if context["mime"] else 1
        for card in held:
            if card["value"]["rank"] == rank:
                for _ in range(times):
                    totals["mult"] *= factor
    return apply


def _held_mult_per_rank(rank, bonus):
    def apply(totals, context):
        held = context["held_cards"]
        if held is None:
            raise _Unknown("需要出牌后仍留在手里的牌，局面未提供")
        times = 2 if context["mime"] else 1
        for card in held:
            if card["value"]["rank"] == rank:
                totals["mult"] += bonus * times
    return apply


def _held_all_suits_x_mult(suits, factor):
    """黑板：留在手里的牌必须全是指定花色；手里没有牌时条件成立。"""
    def apply(totals, context):
        held = context["held_cards"]
        if held is None:
            raise _Unknown("需要出牌后仍留在手里的牌，局面未提供")
        def counts(card):
            enhancement = str((card.get("modifier") or {}).get("enhancement") or "").upper()
            if enhancement == "WILD" and not _card_is_debuffed(card):
                return True  # card.lua 的 is_suit：万能牌符合任何花色
            if enhancement == "STONE":
                return False  # 石头牌没有花色
            return any(_is_suit(card, s, context) for s in suits)
        if all(counts(card) for card in held):
            totals["mult"] *= factor
    return apply


def _held_lowest_rank_mult():
    """举起的拳头：按手里最小点数的两倍加倍率。"""
    def apply(totals, context):
        held = context["held_cards"]
        if held is None:
            raise _Unknown("需要出牌后仍留在手里的牌，局面未提供")
        if not held:
            return
        values = [RANK_VALUES[card["value"]["rank"]] for card in held]
        times = 2 if context["mime"] else 1
        totals["mult"] += 2 * min(values) * times
    return apply


def _misprint_bounded():
    """误打误撞：公开范围已给上下界，按边界取值。"""
    def apply(totals, context):
        value = context["joker"].get("value") or {}
        low, high = value.get("random_mult_min"), value.get("random_mult_max")
        if type(low) not in (int, float) or type(high) not in (int, float):
            raise _Unknown("误打误撞的公开范围未提供")
        totals["bounded"] = low != high
        totals["mult"] += high if context["bound"] == "high" else low
    return apply


def _rank_mult(ranks, bonus):
    def apply(card, totals, _context):
        if card["value"]["rank"] in ranks:
            totals["mult"] += bonus
    return apply


def _even_rank_mult(bonus):
    def apply(card, totals, _context):
        if card["value"]["rank"] in EVEN_RANKS:
            totals["mult"] += bonus
    return apply


def _supernova(totals, context):
    """game.lua 先把本手牌型的 played 自增，再由 Supernova 读取，因此是自增后的值。"""
    played = (context["poker_hands"].get(context["hand_type"]) or {}).get("played")
    if type(played) is not int:
        raise _Unknown("缺少该牌型的公开出牌次数")
    totals["mult"] += played + 1


def _mult_per_joker(bonus):
    def apply(totals, context):
        totals["mult"] += bonus * context["joker_count"]
    return apply


def _leading_chips(label):
    def apply(totals, context):
        totals["chips"] += _current_value(context["joker"], LEADING_ADD_CHIPS, label)
    return apply


def _leading_mult(label):
    def apply(totals, context):
        totals["mult"] += _current_value(context["joker"], LEADING_ADD_MULT, label)
    return apply


def _mult_when_no_discards_left(bonus):
    """剩余弃牌为 0 时加倍率。弃牌数未知（例如商店里的假设计算）时给区间。"""
    def apply(totals, context):
        remaining = (context["round_state"] or {}).get("discards_left")
        if type(remaining) is int:
            if remaining == 0:
                totals["mult"] += bonus
            return
        totals["bounded"] = True
        if context["bound"] == "high":
            totals["mult"] += bonus
    return apply


def _chips_per_remaining_discard(bonus):
    """每剩余一次弃牌加筹码。弃牌数未知时给区间，上界按手牌上限对应的最大弃牌数无法确定，
    因此只在已知弃牌数时给值，未知时判未知而不是猜一个上界。"""
    def apply(totals, context):
        remaining = (context["round_state"] or {}).get("discards_left")
        if type(remaining) is not int:
            raise _Unknown("旗帜需要本轮剩余弃牌数，当前局面未提供")
        totals["chips"] += bonus * remaining
    return apply


# 累加漂移的相对宽度。0.1 与 0.01 在二进制里都不精确，而成长型乘算每回合累加
# 一次，几十次之后存储值会与同名的十进制数差若干个 ulp；卡面又是四舍五入后的值，
# 所以精确值不可知。最终得分取 floor(筹码 × 倍率)，差一个 ulp 就差一分。
# 2**-45 对 1.2 约为 3e-14（上百个 ulp），足以覆盖现实局数的漂移。
ACCUMULATION_DRIFT = 2 ** -45


def _accumulated_from(start, step, times):
    """复现游戏里逐次加减得到的浮点值；两边都是 IEEE 双精度，顺序一致即同值。"""
    value = start
    for _ in range(times):
        value += step
    return value


def _accumulates_exactly(step):
    """这个步长反复加减会不会有累计误差。

    只有二进制里能精确表示的步长（0.25、0.5、整数这类二进制分数）才不会；
    0.1、0.2、0.01 都会。十进制能写出来不等于二进制能精确表示——
    吸血鬼那一分之差就是把这两件事混为一谈造成的。
    """
    return float(abs(step) * 4).is_integer()


def _leading_x_mult(label, start=None, step=None):
    """卡面开头给出的当前乘算倍率。

    该值在游戏里由反复加减同一步长得到，直接按卡面小数相乘会有偏差：实测拉面
    显示 X1.61 时内部为 1.6099999999999997，相乘后 floor 会差 1 分。

    步长在二进制里精确时按累加复现即可，两边同序同值。不精确时**只能给区间**：
    卡面是四舍五入到两位小数的，而同一个显示值对应多个相差若干 ulp 的存储值，
    累加路径（分几次、每次几步）又无法从公开信息还原。实测拉面显示 X1.95 时，
    任何一条我们能想到的路径都算出 2106，游戏结算 2105。
    """
    def apply(totals, context):
        shown = _current_value(context["joker"], LEADING_X_MULT, label)
        if start is None or step is None:
            totals["mult"] *= shown
            return
        times = round((shown - start) / step)
        if times < 0 or round(_accumulated_from(start, step, times), 2) != round(shown, 2):
            raise _Unknown("%s 的当前乘算倍率无法还原成累加结果" % label)
        value = _accumulated_from(start, step, times)
        # The Hook 这类 Boss 每打出一手就强制弃掉几张牌，而按弃牌衰减的小丑
        # 会被它改掉。实测 The Hook 配拉面：卡面 X2，游戏按 X1.98 结算
        # （62 × 17 × 1.98 = 2086.92，floor 2086；按 X2 算是 2108）。
        # 那几张弃在本手计分之前还是之后，公开信息看不出来，所以给区间。
        forced = forced_discards_per_hand(context.get("blinds")) if step < 0 else 0
        low = _accumulated_from(value, step, forced) if forced else value
        if times == 0 and not forced:
            totals["mult"] *= value
            return
        if _accumulates_exactly(step):
            totals["mult"] *= low if context["bound"] == "low" else value
            totals["bounded"] = forced > 0
            return
        spread = value * ACCUMULATION_DRIFT
        totals["mult"] *= (low - low * ACCUMULATION_DRIFT
                           if context["bound"] == "low" else value + spread)
        totals["bounded"] = True
    return apply


def _displayed_add_mult(label):
    def apply(totals, context):
        totals["mult"] += _current_value(context["joker"], CURRENT_ADD_MULT, label)
    return apply


def _midas_mask(totals, context):
    """card.lua:3443：在 context.before 把计分集合里的人头牌换成金卡。

    金卡只有 h_dollars，不加筹码也不加倍率，所以普通人头牌被换掉后对本手计分没有
    影响——基础点数照算。但被换掉的牌会丢掉原来的强化，若那张牌带着奖励筹码、
    加算倍率或乘算，换成金卡后这些就不存在了，而局面给的仍是换之前的数值。
    这种情况无法从公开信息还原，判未知。
    """
    for card in context["scoring"]:
        if not _is_face(card, context):
            continue
        modifier = card.get("modifier") or {}
        if any(_numeric(modifier.get(field)) for field in
               ("bonus", "perma_bonus", "mult", "x_mult")):
            raise _Unknown("迈达斯面具会把带数值加成的人头牌换成金卡，原数值无从还原")


def _loyalty_x_mult(factor):
    """card.lua:3632 先重算 loyalty_remaining：等于 0 时只显示「即将激活」，
    等于周期上限（5）时才真正返回 X4。因此「归零那手给 X4」是错的说法。
    卡面剩余 >= 2 时本手确定不触发；剩余 <= 1 时重算结果可能落在本手之内，判未知。"""
    def apply(totals, context):
        effect = (context["joker"].get("value") or {}).get("effect") or ""
        found = LOYALTY_REMAINING.search(effect)
        if not found or int(found.group(1)) <= 1:
            raise _Unknown("忠诚卡本手是否触发无法确定")
    return apply


def _displayed_plain_mult(label):
    def apply(totals, context):
        totals["mult"] += _current_value(context["joker"], CURRENT_PLAIN_ADD, label)
    return apply


def _exact_x_mult(label):
    """步长为 0.5 或整数的成长乘算：卡面一位小数就是精确值，不必给区间。"""
    def exact(totals, context):
        totals["mult"] *= _current_value(context["joker"], CURRENT_X_MULT, label)
    return exact


def _chance_x_mult_on_suit(suit, factor):
    """card.lua:3247 在逐牌效果里按概率对该花色的牌乘算，重触发时每次都重算。

    两种结果都确定，取「全不触发」为下界、「每次都触发」为上界。
    """
    def apply(card, totals, context):
        if _card_is_debuffed(card) or _is_stone(card):
            return
        if not _is_suit(card, suit, context):
            return
        if context["bound"] == "high":
            totals["mult"] *= factor
        totals["bounded"] = True
    return apply


def _lucky_cat(totals, context):
    """card.lua:3076：每次幸运牌触发，幸运猫当场 +X0.25，并用成长后的值计分。

    触发与否随机，因此下界取卡面（四舍五入的下沿），上界按本手全部幸运牌都触发计。
    """
    shown = _current_value(context["joker"], CURRENT_X_MULT, "幸运猫")
    lucky = sum(1 for card in context["scoring"]
                if str((card.get("modifier") or {}).get("enhancement") or "").upper()
                == "LUCKY")
    if context["bound"] == "high":
        totals["mult"] *= shown + 0.05 + 0.25 * lucky
    else:
        totals["mult"] *= max(1.0, shown - 0.05)
    totals["bounded"] = True


WEE_CHIP_STEP = 8      # game.lua: j_wee 的 chip_mod
VAMPIRE_STEP = 0.1     # game.lua: j_vampire 的 extra


def _wee_joker(totals, context):
    """card.lua:3083 在 context.individual 里，每张计分的 2 先让它 +8 筹码；
    3873 的主效果读的是**累加之后**的值。逐牌事件在小丑阶段之前，
    因此本手打出的每张 2（含重触发）都已经计入。
    """
    twos = context["scored_two_triggers"]
    shown = _current_value(context["joker"], CURRENT_ADD_CHIPS, "小丑娃娃")
    totals["chips"] += shown + WEE_CHIP_STEP * twos


def _vampire(totals, context):
    """card.lua:3465 在 context.before：吸走计分牌上的强化并按张数 +X0.1。

    被吸走的牌本手按无强化计分，这一点在计分牌循环里单独处理。

    乘算按区间算，不取卡面的确定值：步长 0.1 在二进制里不精确，
    `x_mult += extra * #enhanced` 每手累加一次，存储值会与十进制的同名数差
    若干个 ulp，而最终得分是 floor(筹码 × 倍率)——差一个 ulp 就差一分。
    实测一手 60 × 22.8：按卡面算得 1368，游戏结算 1367。
    历史累加路径无法从公开信息还原，所以这里只能给区间。
    """
    shown = _current_value(context["joker"], CURRENT_X_MULT, "吸血鬼")
    # card.lua:3468 第一张吸血鬼处理时就把强化移除并标记，后面的吸不到。
    taken = context["vampired_count"] if not context["vampire_used"] else 0
    context["vampire_used"] = True
    nominal = shown + VAMPIRE_STEP * taken
    if nominal == 1.0:
        totals["mult"] *= 1.0      # 显示 X1 只能来自初始值，没有累加过
        return
    spread = nominal * ACCUMULATION_DRIFT
    totals["mult"] *= (nominal - spread if context["bound"] == "low"
                       else nominal + spread)
    totals["bounded"] = True


def _joker_stencil(totals, context):
    """card.lua:4203：X 倍率等于空小丑槽数加上场上小丑模板的张数；

    card.lua:3966 另有一道门槛——只有在确实存在空槽时才返回乘算，
    槽位坐满时即使 x_mult 不为零也不生效。槽位数来自公开的小丑区域信息。
    """
    state = context["round_state"] or {}
    limit, count = state.get("joker_limit"), state.get("joker_count")
    if type(limit) is not int or type(count) is not int:
        raise _Unknown("需要小丑槽位总数与当前张数，局面未提供")
    empty = limit - count
    if empty <= 0:
        return
    stencils = sum(1 for joker in context["jokers"]
                   if joker.get("key") == "j_stencil")
    totals["mult"] *= empty + stencils


def _joker_stencil_placeholder():
    pass


def _bounded_x_mult(label, step=None):
    """卡面只给一位小数，存储值因此落在 ±0.05 的区间内；按当前边界取值。

    显示 X1 只能来自初始值或重置，是精确的 1.0。step 不为空时表示这张小丑会在
    打出这手牌之前先成长一步（如方尖碑），成长同样按边界传播。
    """
    def apply(totals, context):
        shown = _current_value(context["joker"], CURRENT_X_MULT, label)
        if shown == 1.0 and step is None:
            totals["mult"] *= 1.0
            return
        low, high = shown - 0.05, shown + 0.05
        if shown == 1.0:
            low = high = 1.0
        if step is not None:
            low, high = low + step, high + step
        totals["mult"] *= low if context["bound"] == "low" else high
        totals["bounded"] = True
    return apply


def _repeat_hand_x_mult(factor):
    """card.lua 判断 played_this_round > 1，而该计数在本手开始时已自增，
    因此等价于「本轮此前已打过这个牌型」。"""
    def apply(totals, context):
        played = (context["poker_hands"].get(context["hand_type"]) or {}).get(
            "played_this_round")
        if type(played) is not int:
            raise _Unknown("缺少该牌型本轮的公开出牌次数")
        if played >= 1:
            totals["mult"] *= factor
    return apply


# game.lua 的 l_chips / l_mult：升一级给的筹码与倍率。太空小丑按概率在计分前升级，
# 取「不升」与「升一级」两端即得严格区间。
HAND_LEVEL_GAINS = {"High Card": (10, 1), "Pair": (15, 1), "Two Pair": (20, 1),
                    "Three of a Kind": (20, 2), "Straight": (30, 3),
                    "Flush": (15, 2), "Full House": (25, 2),
                    "Four of a Kind": (30, 3), "Straight Flush": (40, 4),
                    "Five of a Kind": (35, 3), "Flush House": (40, 4),
                    "Flush Five": (50, 3)}
LUCKY_MULT = 20          # m_lucky 的 config.mult，按 1/5 概率触发
BLOODSTONE_X_MULT = 1.5  # j_bloodstone 的 Xmult，对每张红桃按 1/2 概率触发

BASEBALL_FACTOR = 1.5
HIKER_CHIPS = 5


def _x_mult_per_uncommon_joker(factor):
    """棒球卡自身不在它的位置上结算。

    card.lua:3396 通过 context.other_joker 在**每张罕见小丑自己被结算时**返回 X1.5，
    因此乘算要落在那张小丑的位置上，而不是集中到棒球卡这里。这里只负责校验稀有度
    是否已上报，真正的乘算在小丑主循环里按位置施加。

    说明：当前回放语料里与棒球卡同场的罕见小丑只有公牛（只加筹码），两种顺序结果
    相同，因此这条顺序由源码推导得出，尚无回放反例可资验证。
    """
    def apply(totals, context):
        for other in context["jokers"]:
            if other is context["joker"]:
                continue
            if not other.get("rarity_label"):
                raise _Unknown("小丑稀有度缺失，棒球卡收益无法确定")
    return apply


def _growing_chips_if_contains(hand_type, step, label):
    """本手满足条件时，这张小丑在计分前先成长一步，主效果用的是增长后的值。"""
    def apply(totals, context):
        grown = step if hand_type in context["contains"] else 0
        totals["chips"] += _current_value(context["joker"], CURRENT_ADD_CHIPS, label) + grown
    return apply


def _growing_mult_if_contains(hand_types, step, label):
    def apply(totals, context):
        grown = step if any(name in context["contains"] for name in hand_types) else 0
        totals["mult"] += _current_value(context["joker"], CURRENT_ADD_MULT, label) + grown
    return apply


def _displayed_chips(label):
    """卡面已给出当前筹码加成（蓝色小丑按剩余牌数实时计算，卡面同样公开该值）。"""
    def apply(totals, context):
        totals["chips"] += _current_value(context["joker"], CURRENT_ADD_CHIPS, label)
    return apply


def _growing_chips_on_exact_size(step, size, label):
    def apply(totals, context):
        grown = step if context["played_count"] == size else 0
        totals["chips"] += _current_value(context["joker"], CURRENT_ADD_CHIPS, label) + grown
    return apply


def _flat_mult(bonus):
    def apply(totals, _context):
        totals["mult"] += bonus
    return apply


def _small_hand_mult(bonus, max_cards):
    def apply(totals, context):
        if context["played_count"] <= max_cards:
            totals["mult"] += bonus
    return apply


def _ride_the_bus(totals, context):
    """card.lua（context.before）：计分牌里只要有人头牌就清零，否则本手先 +1。

    人头判定走 is_face()，因此受空想小丑影响；清零分支是精确的 0，不是卡面值。
    """
    if any(_is_face(card, context) for card in context["scoring"]):
        return
    totals["mult"] += _current_value(context["joker"], CURRENT_ADD_MULT, "坐公交") + 1


def _growing_add_mult(step, label):
    """卡面显示值加上本手开始时的成长步长；步长为 0 表示本手不会先增长。"""
    def apply(totals, context):
        totals["mult"] += _current_value(context["joker"], CURRENT_ADD_MULT, label) + step
    return apply


def _obelisk(totals, context):
    """复现 card.lua 的方尖碑重置分支。

    游戏在 state_events.lua 先把本手牌型的 played 自增，再在 context.before 判断：
    若没有别的已显示牌型的出牌次数达到这个新值，就把乘算重置为 X1；否则按步长成长。
    重置分支是精确的 1.0。成长分支依赖游戏内逐回合累加的浮点值，而卡面只给四舍五入
    后的一位小数：显示 X1 只可能来自重置赋值的精确 1.0，累加一次没有累计误差，可以算；
    显示更大的值无法还原累加次数与误差——实测 13 手里有一手因此差 1 分，判为未知。
    """
    hands = context["poker_hands"]
    played = (hands.get(context["hand_type"]) or {}).get("played")
    if type(played) is not int:
        raise _Unknown("缺少该牌型的公开出牌次数，不能判断方尖碑是否重置")
    played_after = played + 1
    for name, info in hands.items():
        if name != context["hand_type"] and (info.get("played") or 0) >= played_after:
            _bounded_x_mult("方尖碑", OBELISK_STEP)(totals, context)
            return
    totals["mult"] *= 1


SCORED_CARD_EFFECTS = {
    "j_bloodstone": _chance_x_mult_on_suit("H", BLOODSTONE_X_MULT),
    "j_greedy_joker": _suit_mult("D", 3),
    "j_lusty_joker": _suit_mult("H", 3),
    "j_wrathful_joker": _suit_mult("S", 3),
    "j_gluttenous_joker": _suit_mult("C", 3),
    "j_photograph": _first_face_x_mult(2),
    "j_walkie_talkie": _rank_chips_and_mult(("T", "4"), 10, 4),
    "j_scholar": _rank_chips_and_mult(("A",), 20, 4),
    "j_even_steven": _even_rank_mult(4),
    # card.lua 判断点数 2、3、5、8、14（A）。
    "j_fibonacci": _rank_mult(("A", "2", "3", "5", "8"), 8),
    "j_odd_todd": _rank_chips(ODD_RANKS, 31),
    "j_scary_face": _face_chips(30),
    "j_smiley": _face_mult(5),
    "j_arrowhead": _suit_chips("S", 50),
    "j_onyx_agate": _suit_mult("C", 7),
    "j_triboulet": _rank_x_mult(("K", "Q"), 2),
    "j_idol": _idol_x_mult(2),
    "j_ancient": _rank_x_mult_by_effect_suit(1.5, "远古小丑"),
}
HAND_EFFECTS = {
    "j_wee": _wee_joker,
    "j_vampire": _vampire,
    "j_space": lambda totals, context: None,  # 升级已在起始值按边界计入
    "j_sly": _contains_chips("Pair", 50),
    "j_wily": _contains_chips("Three of a Kind", 100),
    "j_clever": _contains_chips("Two Pair", 80),
    "j_devious": _contains_chips("Straight", 100),
    "j_crafty": _contains_chips("Flush", 80),
    "j_jolly": _contains_mult("Pair", 8),
    "j_zany": _contains_mult("Three of a Kind", 12),
    "j_mad": _contains_mult("Two Pair", 10),
    "j_crazy": _contains_mult("Straight", 12),
    "j_droll": _contains_mult("Flush", 10),
    "j_blue_joker": _displayed_chips("蓝色小丑"),
    "j_square": _growing_chips_on_exact_size(4, 4, "方块小丑"),
    "j_joker": _flat_mult(4),
    "j_cavendish": _fixed_x_mult(3),
    "j_duo": _contains_x_mult("Pair", 2),
    "j_trio": _contains_x_mult("Three of a Kind", 3),
    "j_family": _contains_x_mult("Four of a Kind", 4),
    "j_order": _contains_x_mult("Straight", 3),
    "j_tribe": _contains_x_mult("Flush", 2),
    "j_flower_pot": _all_suits_x_mult(3),
    "j_seeing_double": _club_and_other_x_mult(2),
    "j_acrobat": _x_mult_on_final_hand(3),
    "j_stuntman": _flat_chips(250),
    "j_bull": _chips_per_dollar(2),
    "j_bootstraps": _mult_per_dollars(2, 5),
    "j_swashbuckler": _mult_from_other_sell_values(),
    "j_misprint": _misprint_bounded(),
    "j_baron": _held_x_mult_per_rank("K", 1.5),
    "j_shoot_the_moon": _held_mult_per_rank("Q", 13),
    "j_blackboard": _held_all_suits_x_mult(("S", "C"), 3),
    "j_raised_fist": _held_lowest_rank_mult(),
    "j_supernova": _supernova,
    "j_card_sharp": _repeat_hand_x_mult(3),
    "j_baseball": _x_mult_per_uncommon_joker(1.5),
    "j_abstract": _mult_per_joker(3),
    "j_fortune_teller": _displayed_plain_mult("占卜师"),
    "j_mystic_summit": _mult_when_no_discards_left(15),
    "j_banner": _chips_per_remaining_discard(30),
    "j_drivers_license": _bounded_fixed_x_mult(1, 3),
    "j_hologram": _bounded_x_mult("全息影像"),
    # 拉面从 X2 起每弃一张牌减 0.01（game.lua: Xmult = 2, extra = 0.01）。
    "j_ramen": _leading_x_mult("拉面", 2.0, -0.01),
    "j_caino": _bounded_x_mult("小丑卡伊诺"),
    "j_glass": _bounded_x_mult("玻璃小丑"),
    "j_hit_the_road": _bounded_x_mult("上路"),
    "j_lucky_cat": _lucky_cat,
    # game.lua:436 的成长步长为 0.5，卡面一位小数足以精确表示，不需要区间。
    "j_madness": _exact_x_mult("疯狂"),
    "j_yorick": _bounded_x_mult("约里克"),
    "j_throwback": _bounded_x_mult("回溯"),
    "j_steel_joker": _bounded_x_mult("钢铁小丑"),
    "j_stencil": _joker_stencil,
    "j_castle": _displayed_chips("城堡"),
    # card.lua:3435：本手包含顺子时，奔跑者在计分前先 +15 筹码，主效果读的是增长后的值。
    "j_runner": _growing_chips_if_contains("Straight", 15, "奔跑者"),
    "j_stone": _displayed_chips("石头小丑"),
    "j_ceremonial": _displayed_add_mult("祭礼之刃"),
    "j_ride_the_bus": _ride_the_bus,
    # card.lua:3412：本手包含两对或葫芦时，备用裤子在计分前先 +2 倍率。
    "j_trousers": _growing_mult_if_contains(("Two Pair", "Full House"), 2, "备用裤子"),
    "j_erosion": _displayed_add_mult("侵蚀"),
    "j_flash": _displayed_add_mult("闪卡"),
    "j_loyalty_card": _loyalty_x_mult(4),
    "j_midas_mask": _midas_mask,
    "j_ice_cream": _leading_chips("冰淇淋"),
    "j_popcorn": _leading_mult("爆米花"),
    "j_constellation": _bounded_x_mult("星座"),
    "j_campfire": _bounded_x_mult("营火"),
    "j_half": _small_hand_mult(20, 3),
    "j_gros_michel": _flat_mult(15),
    "j_green_joker": _growing_add_mult(1, "绿色小丑"),
    "j_red_card": _growing_add_mult(0, "红牌"),
    "j_obelisk": _obelisk,
}
# 卡面效果与一手牌的筹码、倍率无关。
# 四根手指与捷径只改变判型规则（见 plain_hand_type），对筹码与倍率没有贡献。
# 逐条核对英文卡面效果后确认对单手筹码与倍率没有贡献的小丑：
# 只产生金钱、改变槽位或手牌上限、创建卡牌、修改牌组、改变概率、或在出售与死亡时生效。
NO_SCORING_EFFECT = (
    "j_luchador", "j_mail", "j_egg", "j_drunkard", "j_turtle_bean",
    "j_four_fingers", "j_shortcut", "j_credit_card", "j_riff_raff",
    # 金钱类
    "j_delayed_grat", "j_faceless", "j_todo_list", "j_vagabond", "j_cloud_9",
    "j_rocket", "j_gift", "j_to_the_moon", "j_golden", "j_trading", "j_ticket",
    "j_rough_gem", "j_matador", "j_satellite", "j_business", "j_reserved_parking",
    # 槽位与手牌上限类
    "j_juggler", "j_troubadour", "j_merry_andy", "j_burglar",
    # 创建卡牌与牌组操作类
    "j_dna", "j_superposition", "j_diet_cola", "j_cartomancer", "j_astronomer",
    "j_marble", "j_chaos", "j_sixth_sense", "j_hallucination", "j_certificate",
    "j_8_ball", "j_perkeo", "j_invisible", "j_burnt",
    # 其它：改概率、允许重复、防死、把计分后的人头牌变成金卡（金卡本身不计分）
    "j_hiker",
    "j_oops", "j_ring_master", "j_mr_bones", "j_seance", "j_chicot",
    # 涂抹小丑本身不加分：它的作用通过 context["smeared"] 进入判型与所有花色条件
    "j_smeared",
)
# 丑脸小丑让所有牌都算人头牌，影响照片、惊悚脸、笑脸与戏剧面具。
FACE_OVERRIDE = ("j_pareidolia",)
# 飞溅让打出的每张牌都参与计分，而不只是组成牌型的那几张。
SCORING_SET_OVERRIDE = ("j_splash",)
# 让每张计分牌额外结算一次；卡面公开剩余手数，持有即生效。
RETRIGGER_JOKERS = {"j_selzer": 1}
# 只让特定点数的计分牌多结算一次。
PER_CARD_RETRIGGERS = {"j_hack": (("2", "3", "4", "5"), 1)}
# 按条件决定是否整手重触发的小丑：黄昏只在本轮最后一手生效。
CONDITIONAL_RETRIGGERS = {"j_dusk": "final_hand"}
# 只对人头牌重触发。
FACE_RETRIGGERS = {"j_sock_and_buskin": 1}
# 只对计分集合里的第一张牌额外重触发。
FIRST_CARD_RETRIGGERS = {"j_hanging_chad": 2}
# 哑剧让手牌持有类效果再触发一次；它本身不改变打出牌的计分。
HELD_RETRIGGERS = ("j_mime",)
# card.lua 把这几张放在 context.individual 的 G.hand 分支：逐张留在手里的牌结算，
# **早于**小丑主效果。放在小丑阶段会让乘算排到加算之后，算出的分数偏高：
# 5687310B 第 83 步按小丑阶段算 4950，按留手阶段算 4550，后者与游戏结算一致。
HELD_CARD_JOKERS = {"j_baron": ("K", "x", 1.5),
                    "j_shoot_the_moon": ("Q", "+", 13)}
LOWEST_HELD_JOKERS = ("j_raised_fist",)
# 逐条核对后确认无法由公开信息确定的小丑，以及原因。
CANNOT_DETERMINE = {
    "j_cavendish_random": "占位",
    # 回放反例：115A3B01 第 101 步卡面写「Currently +1 Mult」，实际结算的倍率
    # 比按卡面计算少 1（187 × 29 = 5423，而按卡面为 187 × 30 = 5610）。
    "j_green_joker": "卡面当前值与结算时实际生效的值出现过不一致，成因未查清",
    # 补上留手牌后首次能算，而首例即不符：5687310B 第 83 步算得 5100、实得 4550。
    # 可能是男爵本身，也可能是同阵容的超新星计数时机，未区分前不给数。

    # 92E12179 第 120 步：改为精确乘算后倍率已与结算完全一致（31.5），
    # 只剩筹码差 8——我们算 392，实际 384。拆开看 160 基础 + 24 牌面 + 90 旗帜
    # + 68 公牛（现金 34）+ 50 狡猾；若公牛按现金 30 计正好是 384。疯狂本身不加
    # 筹码（card.lua:3653），所以问题不在它，而在同阵容的公牛或牌面计数。
    # 需要受控实验区分，在此之前这套阵容不给数。
    "j_madness": "同阵容筹码侧与结算差 8（倍率侧已验证正确），成因未查清",
}
CANNOT_DETERMINE.pop("j_cavendish_random", None)
# 打出时对筹码与倍率没有贡献的强化（game.lua：金卡只有 h_dollars，钢铁卡只有 h_x_mult，
# 两者都只在牌留在手里时生效）。会改变计分的 BONUS、MULT、GLASS、LUCKY 仍判未知。
# 金卡只有 h_dollars、钢铁卡只有 h_x_mult，打出时对计分没有贡献。
SCORE_NEUTRAL_ENHANCEMENTS = ("GOLD", "STEEL")
# 幸运牌的倍率按概率触发（card.lua get_chip_mult 里走 pseudorandom），无法确定。
# 鎏金为 +50 筹码（game.lua e_foil extra=50），负片只给槽位、不参与计分。
# 筹码是加算量，与其它效果的先后无关，因此不受小丑顺序影响。
# game.lua:660-662 鎏金 +50 筹码、全息 +10 倍率、多彩 X1.5；负片只给槽位不计分。
# state_events.lua:880-940 的顺序是：版本筹码 → 版本加算倍率 → 小丑自身效果
# → 其它小丑的反应（棒球卡）→ 版本乘算倍率。
JOKER_EDITIONS = {"FOIL": (50, 0, 1.0), "HOLO": (0, 10, 1.0),
                  "POLYCHROME": (0, 0, 1.5), "NEGATIVE": (0, 0, 1.0)}


# game.lua 的 blueprint_compat：这些小丑不能被蓝图或头脑风暴复制。
NOT_COPYABLE = frozenset((
    "j_four_fingers", "j_credit_card", "j_chaos", "j_delayed_grat", "j_pareidolia",
    "j_egg", "j_splash", "j_sixth_sense", "j_shortcut", "j_cloud_9", "j_rocket",
    "j_midas_mask", "j_gift", "j_turtle_bean", "j_to_the_moon", "j_juggler",
    "j_drunkard", "j_golden", "j_trading", "j_mr_bones", "j_troubadour",
    "j_smeared", "j_ring_master", "j_merry_andy", "j_oops", "j_invisible",
    "j_satellite", "j_astronomer", "j_chicot"))
# 蓝图复制右边那张（card.lua:2307），头脑风暴复制最左那张（card.lua:2322）。
COPY_JOKERS = {"j_blueprint": "right", "j_brainstorm": "leftmost"}
MAX_COPY_DEPTH = 5


def resolve_copies(jokers, keys):
    """每个位置实际生效的小丑：蓝图与头脑风暴换成它们复制的那张。

    复制链可以接力（蓝图复制蓝图），用深度上限防环。复制不到、
    或目标在 blueprint_compat 名单之外时，这个位置本手不产生效果。
    """
    resolved = []
    for index, key in enumerate(keys):
        position, joker, depth = index, jokers[index], 0
        while keys[position] in COPY_JOKERS and depth < MAX_COPY_DEPTH:
            target = (position + 1 if COPY_JOKERS[keys[position]] == "right" else 0)
            if target == position or not 0 <= target < len(keys):
                position, joker = None, None
                break
            position, joker, depth = target, jokers[target], depth + 1
        if position is None or keys[position] in COPY_JOKERS:
            resolved.append((None, None))          # 复制不到任何东西
        elif keys[position] in NOT_COPYABLE and index != position:
            resolved.append((None, None))          # 该效果不可被复制
        else:
            resolved.append((keys[position], joker))
    return resolved


def blind_zeroes_hand(blinds, round_state, poker_hands, hand_type, played_count):
    """这手牌会不会被盲注判成 0 分（blind.lua:519 的 debuff_hand）。

    三种条件都能从公开局面精确判定，所以应当算出确切的 0，而不是给错数：
    The Psychic 要求至少打五张；The Eye 禁止本轮重复牌型；
    The Mouth 锁定本轮第一手的牌型。锁定的是哪一种由 played_this_round 推断，
    若有多个牌型都打过（说明此前有手被判 0）则无法确定是哪一种，返回未知。
    """
    for blind in (blinds or {}).values():
        if not isinstance(blind, dict) or blind.get("status") != "CURRENT":
            continue
        if blind.get("disabled") is True:
            continue
        name = HAND_RULE_BLIND_NAMES.get(blind.get("key"), None if blind.get("key") else blind.get("name"))
        if name == "The Psychic" and played_count < 5:
            return True
        played = {key: (value or {}).get("played_this_round") or 0
                  for key, value in (poker_hands or {}).items()}
        if name == "The Eye" and played.get(hand_type, 0) >= 1:
            return True
        if name == "The Mouth":
            locked = [key for key, count in played.items() if count >= 1]
            if len(locked) > 1:
                raise _Unknown("The Mouth 已有多个牌型打过，无法判断锁定的是哪一种")
            if locked and locked[0] != hand_type:
                return True
    return False


def _checked_joker(joker):
    key = joker.get("key")
    # 明确列为算不出的，优先级最高：即使效果表里有现成实现，也不能用。
    # 回放校验推翻过的实现必须立刻失效，否则错数会继续产生。
    if key in CANNOT_DETERMINE:
        raise _Unknown("%s：%s" % (key, CANNOT_DETERMINE[key]))
    if (key not in COPY_JOKERS
            and key not in SCORED_CARD_EFFECTS and key not in HAND_EFFECTS
            and key not in NO_SCORING_EFFECT and key not in RETRIGGER_JOKERS
            and key not in PER_CARD_RETRIGGERS
            and key not in SCORING_SET_OVERRIDE
            and key not in CONDITIONAL_RETRIGGERS
            and key not in FACE_RETRIGGERS
            and key not in FACE_OVERRIDE
            and key not in FIRST_CARD_RETRIGGERS
            and key not in HELD_RETRIGGERS):
        raise _Unknown("未收录的小丑效果：%s" % key)
    edition = (joker.get("modifier") or {}).get("edition")
    if edition and str(edition).upper() not in JOKER_EDITIONS:
        raise _Unknown("小丑带 %s 版本，计分收益未收录：%s" % (edition, key))
    if (joker.get("state") or {}).get("debuff"):
        raise _Unknown("小丑被禁用：%s" % key)
    return key


def score_plain_play(cards, jokers, poker_hands, round_state=None, blinds=None,
                     held_cards=None):
    """返回得分；只能确定在区间内时给 score_min 与 score_max，确定时另给 score。

    cards 必须按打出顺序（即手牌从左到右）排列。公开信息不足时返回 None。
    倍率只会被加正数或乘正数，对边界单调递增，因此分别用下界和上界各算一遍
    即得到严格区间，无需区间算术。
    """
    try:
        low = _score(cards, jokers, poker_hands, bound="low",
                     round_state=round_state, blinds=blinds, held_cards=held_cards)
        high = _score(cards, jokers, poker_hands, bound="high",
                      round_state=round_state, blinds=blinds, held_cards=held_cards)
    except _Unknown:
        return None
    result = dict(high)
    result["score_min"] = low["score"]
    result["score_max"] = high["score"]
    if low["score"] == high["score"]:
        result["score"] = low["score"]
    else:
        result.pop("score", None)
        result["score_is_bounded_not_exact"] = True
    return result


def unknown_reason(cards, jokers, poker_hands, round_state=None, blinds=None,
                   held_cards=None):
    """给出无法确定得分的原因，便于复盘时区分数据缺失与规则未收录。"""
    try:
        _score(cards, jokers, poker_hands, bound="low", round_state=round_state,
               blinds=blinds, held_cards=held_cards)
    except _Unknown as reason:
        return str(reason)
    return None


def _score(cards, jokers, poker_hands, bound="low", round_state=None,
           blinds=None, held_cards=None):
    if blinds_alter_scoring(blinds, round_state):
        raise _Unknown("当前盲注会改变基础计分，单手得分无法确定")
    classified = classify_plain_hand(cards, jokers)
    if classified is None:
        raise _Unknown("牌型无法确定")
    hand_type = classified["hand_type"]
    if blind_zeroes_hand(blinds, round_state, poker_hands, hand_type, len(cards)):
        return {"hand_type": hand_type, "chips": 0, "mult": 0, "score": 0,
                "scoring_count": 0, "zeroed_by_blind": True}
    info = poker_hands.get(hand_type)
    if not isinstance(info, dict) or type(info.get("chips")) is not int \
            or type(info.get("mult")) is not int:
        raise _Unknown("缺少该牌型的公开筹码或倍率")
    keys = [_checked_joker(joker) for joker in jokers]
    # 蓝图与头脑风暴在各自的位置上执行被复制那张的效果，所以先解析成实际生效的
    # (效果键, 取数用的小丑卡)，两个循环都按解析结果走。
    effective = resolve_copies(jokers, keys)
    effective_keys = [key for key, _ in effective]
    repetitions = 1 + sum(RETRIGGER_JOKERS[key] for key in keys
                          if key in RETRIGGER_JOKERS)
    for key in keys:
        if CONDITIONAL_RETRIGGERS.get(key) != "final_hand":
            continue
        left = (round_state or {}).get("hands_left")
        if type(left) is not int:
            raise _Unknown("黄昏需要本轮剩余手数，局面未提供")
        if left == 1:
            repetitions += 1
    if (repetitions > 1 or any(key in PER_CARD_RETRIGGERS for key in keys)) \
            and "j_photograph" in keys:
        # 2FD8AF05 第 80 步实测 15,960 分，用重触发与照片的各种组合都无法复现，
        # 说明这一交互还有未掌握的因素；在查清之前判未知，不给估算值。
        raise _Unknown("重触发与照片小丑并存时的结算尚未查清")
    for card in cards:
        modifier = card.get("modifier") or {}
        for field in ("seal", "edition"):
            if modifier.get(field):
                raise _Unknown("出牌中有带 %s 的牌，计分收益未收录" % field)
        enhancement = modifier.get("enhancement")
        # 幸运牌的倍率按概率触发（card.lua get_chip_mult 走 pseudorandom），
        # 但两种结果都确定，取两端即可给区间而不是拒绝。
        if (enhancement and enhancement not in SCORE_NEUTRAL_ENHANCEMENTS
                and not any(type(modifier.get(field)) in (int, float)
                            for field in ("bonus", "perma_bonus", "mult", "x_mult"))):
            # 隔离 Bot 未上报该牌的数值加成时，强化牌无法按公开信息计分。
            raise _Unknown("出牌中有 %s 强化牌，但局面未提供它的数值加成" % enhancement)
    totals = {"chips": info["chips"], "mult": info["mult"], "bounded": False}
    # 吸血鬼在 context.before 吸走计分牌的强化：被吸走的牌本手按普通牌计分，
    # 它自己按吸到的张数成长。两件事都发生在计分之前。
    vampired = set()
    if any(key == "j_vampire" for key in effective_keys):
        for index, card in enumerate(classified["scoring"]):
            modifier = card.get("modifier") or {}
            if modifier.get("enhancement") and not _card_is_debuffed(card):
                vampired.add(id(card))
    space_jokers = sum(1 for key, _ in effective if key == "j_space")
    if space_jokers:
        # card.lua:3420 在 context.before 按 1/4 概率把本手牌型升一级，
        # 升与不升都确定，取两端得区间。
        gain = HAND_LEVEL_GAINS.get(hand_type)
        if gain is None:
            raise _Unknown("太空小丑可能升级的牌型未收录：%s" % hand_type)
        if bound == "high":
            totals["chips"] += gain[0] * space_jokers
            totals["mult"] += gain[1] * space_jokers
        totals["bounded"] = True
    scoring = (list(cards) if any(key in SCORING_SET_OVERRIDE for key in keys)
               else classified["scoring"])
    all_face = any(key in FACE_OVERRIDE for key in keys)
    first_face = next((card for card in scoring
                       if not _card_is_debuffed(card)
                       and (all_face or card["value"]["rank"] in FACE_RANKS)), None)
    context = {"hand_type": hand_type, "poker_hands": poker_hands,
               "all_cards_are_face": all_face, "scoring": scoring,
               "contains": classified["contains"], "joker_count": len(jokers),
               "jokers": jokers, "first_face": first_face, "bound": bound,
               "round_state": round_state, "held_cards": held_cards,
               "blinds": blinds,
               "mime": any(key in HELD_RETRIGGERS for key in keys),
               "smeared": "j_smeared" in keys,
               "played_count": len(cards), "joker": None,
               "vampired_count": len(vampired), "vampire_used": False,
               "scored_two_triggers": 0}
    for card in scoring:
        # state_events.lua 的计分循环跳过被禁用的牌：不给筹码，也不触发计分牌效果。
        if (card.get("state") or {}).get("debuff"):
            continue
        modifier = card.get("modifier") or {}
        card_repetitions = repetitions
        for key in effective_keys:
            retrigger = PER_CARD_RETRIGGERS.get(key)
            if retrigger and card["value"]["rank"] in retrigger[0]:
                card_repetitions += retrigger[1]
            if key in FACE_RETRIGGERS and _is_face(card, context):
                card_repetitions += FACE_RETRIGGERS[key]
            if key in FIRST_CARD_RETRIGGERS and card is scoring[0]:
                card_repetitions += FIRST_CARD_RETRIGGERS[key]
        debuffed = _card_is_debuffed(card)
        if id(card) in vampired:
            # card.lua:3471 的 set_ability(c_base) 只换强化；
            # card.lua:296 明确保留 perma_bonus，蜡封与版本也不受影响。
            modifier = {name: value for name, value in modifier.items()
                        if name in ("perma_bonus", "seal", "edition")}
        # 徒步者在 card.lua:3067 的 context.individual 里给这张牌加 perma_bonus，
        # 发生在它本次筹码结算之后：因此第一次触发不受影响，本手若有重触发，
        # 第二次起每次都带上已累加的部分。两个回放例子分别验证了这两种情形
        # （48F4D0D2 第 70 步无重触发、不加；AEEA6DB2 第 26 步有重触发、要加）。
        hiker_step = sum(HIKER_CHIPS for key in keys if key == "j_hiker")
        # card.lua 的 get_chip_bonus / get_chip_mult / get_chip_x_mult 对被禁用的牌
        # 一律返回 0；石头牌只给 bonus + perma_bonus，不加牌面基础点数。
        stone = str(modifier.get("enhancement") or "").upper() == "STONE"
        for repetition in range(card_repetitions):
            if debuffed:
                continue
            # card.lua:3083 判的是 get_id()==2，而石头牌没有正常点数身份。
            if card["value"]["rank"] == "2" and not _is_stone(card):
                context["scored_two_triggers"] += 1
            base = 0 if stone else BASE_CHIPS[card["value"]["rank"]]
            totals["chips"] += (base + _numeric(modifier.get("bonus"))
                                + _numeric(modifier.get("perma_bonus"))
                                + hiker_step * repetition)
            # 幸运牌上报的 mult 是「触发时」的数值，不是必得的加成，
            # 因此不能无条件计入，只在上界那一侧加。
            if str(modifier.get("enhancement") or "").upper() == "LUCKY":
                amount = _numeric(modifier.get("mult")) or LUCKY_MULT
                if context["bound"] == "high":
                    totals["mult"] += amount
                totals["bounded"] = True
            else:
                totals["mult"] += _numeric(modifier.get("mult"))
            card_x_mult = _numeric(modifier.get("x_mult"))
            if card_x_mult > 1:
                totals["mult"] *= card_x_mult
            for source, (key, joker) in zip(jokers, effective):
                effect = SCORED_CARD_EFFECTS.get(key) if key else None
                if effect:
                    context["joker"] = joker
                    effect(card, totals, context)
    # 留在手里的牌：结算顺序是「打出的牌 → 留在手里的牌 → 小丑」，这一步在小丑之前。
    # 游戏逐张遍历手牌，对每张牌依次结算它自己的强化（钢牌 h_x_mult = 1.5）
    # 与以它为对象的小丑效果，因此加算与乘算的先后由牌的位置决定，不能分两轮算。
    # card.lua:3386 每张哑剧各给一次额外触发，不是「有没有哑剧」的布尔值；
    # card.lua:2242 的红蜡封再额外给一次，且被禁用的牌不触发任何留手效果。
    mime_count = sum(1 for key in effective_keys if key in HELD_RETRIGGERS)
    held_jokers_present = any(key in HELD_CARD_JOKERS or key in LOWEST_HELD_JOKERS
                              for key in effective_keys)
    # 局面没给留手牌时，绝不能当成「手里没有牌」：那会把未知算成精确值。
    if held_cards is None and (held_jokers_present
                               or any(key in HELD_RETRIGGERS for key in effective_keys)):
        raise _Unknown("需要出牌后仍留在手里的牌，局面未提供")
    def held_rank(card):
        rank = ((card.get("value") or {}).get("rank")
                if isinstance(card, dict) else None)
        if rank not in RANK_VALUES:
            # 手里有看不出点数的牌时，以点数为条件的留手小丑无从判断。
            raise _Unknown("留在手里的牌缺少公开点数")
        return rank
    lowest_held = None
    if held_cards and held_jokers_present:
        # card.lua:3321 按 base.id 找最小，用 >= 比较因而同点数取最后一张，
        # 并跳过石头牌；加到倍率上的是该牌的 nominal（即基础筹码）的两倍。
        candidates = [card for card in held_cards
                      if not _is_stone(card) and not _card_is_debuffed(card)]
        for card in candidates:
            if lowest_held is None or (RANK_ORDER_IDS[held_rank(card)]
                                       <= RANK_ORDER_IDS[held_rank(lowest_held)]):
                lowest_held = card
    for card in (held_cards or []):
        if _card_is_debuffed(card):
            continue
        if _is_stone(card) and held_jokers_present:
            continue  # 石头牌没有点数身份，不触发按点数判定的留手小丑
        rank = held_rank(card) if held_jokers_present else None
        held_enhancement = str((card.get("modifier") or {}).get("enhancement") or "").upper()
        red_seal = str((card.get("modifier") or {}).get("seal") or "").upper() == "RED"
        for _ in range(1 + mime_count + (1 if red_seal else 0)):
            if held_enhancement == "STEEL":
                totals["mult"] *= 1.5
            for key, joker in effective:
                wanted = HELD_CARD_JOKERS.get(key)
                if wanted and rank == wanted[0]:
                    if wanted[1] == "x":
                        totals["mult"] *= wanted[2]
                    else:
                        totals["mult"] += wanted[2]
                if key in LOWEST_HELD_JOKERS and card is lowest_held:
                    totals["mult"] += 2 * BASE_CHIPS[rank]
    # 蓝图复制棒球卡时，复制出来的那份同样会对每张罕见小丑生效。
    baseball = sum(1 for key in effective_keys if key == "j_baseball")
    for position, (source, (key, joker)) in enumerate(zip(jokers, effective)):
        edition = str((source.get("modifier") or {}).get("edition") or "").upper()
        edition_chips, edition_mult, edition_x_mult = JOKER_EDITIONS.get(
            edition, (0, 0, 1.0))
        totals["chips"] += edition_chips
        totals["mult"] += edition_mult
        if key and key not in HELD_CARD_JOKERS and key not in LOWEST_HELD_JOKERS:
            effect = HAND_EFFECTS.get(key)  # 留手类已在留手阶段结算
            if effect:
                context["joker"] = joker
                effect(totals, context)
        # 棒球卡看的是实际摆在这个位置的那张牌的稀有度，而不是它复制了谁。
        if baseball and key != "j_baseball" \
                and source.get("rarity_label") == "UNCOMMON":
            for _ in range(baseball):
                totals["mult"] *= BASEBALL_FACTOR
        if edition_x_mult != 1.0:
            totals["mult"] *= edition_x_mult
    return {"hand_type": hand_type, "chips": totals["chips"], "mult": totals["mult"],
            "score": int(totals["chips"] * totals["mult"]),
            "scoring_count": len(scoring)}
