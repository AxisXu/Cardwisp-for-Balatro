"""仅对五张普通明牌判定牌型；依据本机游戏 evaluate_poker_hand 的优先级。"""

from collections import Counter


RANKS = {str(value): value for value in range(2, 10)}
RANKS.update(T=10, J=11, Q=12, K=13, A=14)
# 只有「涂抹小丑」会把花色本身混同，仍判未知；四根手指与捷径按游戏规则实现。
# 涂抹小丑（j_smeared）已按 card.lua 的 is_suit 实现：红桃=方片、黑桃=梅花，见 _flush_group。
HAND_TYPE_MODIFIERS = set()
SAME_COLOR = {"S": ("S", "C"), "C": ("S", "C"), "H": ("H", "D"), "D": ("H", "D")}
SUIT_ORDER = ("S", "H", "C", "D")


def _plain_ranks_and_suits(cards, jokers):
    """只认普通明牌；特殊牌或改变判型的小丑使结果未知。"""
    if not 1 <= len(cards) <= 5 or any(
            isinstance(joker, dict) and joker.get("key") in HAND_TYPE_MODIFIERS
            for joker in jokers):
        return None
    parsed = []
    for card in cards:
        if not isinstance(card, dict) or card.get("hidden"):
            return None
        modifier = card.get("modifier") or {}
        if not isinstance(modifier, dict) or modifier.get("enhancement") in ("WILD", "STONE"):
            return None
        value = card.get("value") or {}
        if not isinstance(value, dict):
            return None
        rank = RANKS.get(value.get("rank"))
        suit = value.get("suit")
        if rank is None or suit not in ("S", "H", "C", "D"):
            return None
        parsed.append((rank, suit))
    return parsed


def _flush_group(parsed, four_fingers, smeared=False):
    """对应游戏 get_flush：按黑桃、红桃、梅花、方片的顺序取第一个达标的花色。

    四根手指把门槛从五张降到四张；计分牌只含该花色的牌，不含其余垫牌。
    涂抹小丑让同色花色互相算作对方（card.lua is_suit），所以按颜色分组。
    """
    needed = 4 if four_fingers else 5
    if not needed <= len(parsed) <= 5:
        return None
    for suit in SUIT_ORDER:
        picked = [index for index, (_, card_suit) in enumerate(parsed)
                  if card_suit == suit or (smeared and card_suit in SAME_COLOR[suit])]
        if len(picked) >= needed:
            return picked
    return None


def _straight_group(parsed, four_fingers, shortcut):
    """对应游戏 get_straight 的扫描：j=1 先查 A，再从 2 扫到 14。

    四根手指把门槛降到四张；捷径允许中间跳过一个点数，但不能跳过 A 那一档。
    """
    needed = 4 if four_fingers else 5
    if not needed <= len(parsed) <= 5:
        return None
    by_rank = {}
    for index, (rank, _) in enumerate(parsed):
        if 1 < rank < 15:
            by_rank.setdefault(rank, []).append(index)
    picked = []
    length = 0
    straight = False
    skipped = False
    for step in range(1, 15):
        rank = 14 if step == 1 else step
        if rank in by_rank:
            length += 1
            skipped = False
            picked.extend(by_rank[rank])
        elif shortcut and not skipped and step != 14:
            skipped = True
        else:
            length = 0
            skipped = False
            if not straight:
                picked = []
            if straight:
                break
        if length >= needed:
            straight = True
    return picked if straight else None


def _same_rank_groups(parsed, size):
    """对应游戏 get_X_same：恰好 size 张同点数的组，按点数从高到低。"""
    counts = Counter(rank for rank, _ in parsed)
    return [rank for rank in sorted(counts, reverse=True) if counts[rank] == size]


def classify_plain_hand(cards, jokers=()):
    """返回牌型与真正参与计分的牌；依据游戏 evaluate_poker_hand 的优先级。

    计分牌按打出顺序返回：游戏逐张遍历打出的牌，只结算属于该牌型的牌。
    """
    parsed = _plain_ranks_and_suits(cards, jokers)
    if parsed is None:
        return None
    ranks = [rank for rank, _ in parsed]
    five = _same_rank_groups(parsed, 5)
    four = _same_rank_groups(parsed, 4)
    three = _same_rank_groups(parsed, 3)
    pairs = _same_rank_groups(parsed, 2)
    keys = {joker.get("key") for joker in jokers if isinstance(joker, dict)}
    flush_indexes = _flush_group(parsed, "j_four_fingers" in keys, "j_smeared" in keys)
    straight_indexes = _straight_group(parsed, "j_four_fingers" in keys,
                                       "j_shortcut" in keys)
    flush = flush_indexes is not None
    straight = straight_indexes is not None

    def by_ranks(*wanted):
        keep = set(wanted)
        return [card for card, (rank, _) in zip(cards, parsed) if rank in keep]

    def by_indexes(indexes):
        return [cards[index] for index in sorted(set(indexes))]

    # 对应 evaluate_poker_hand 的 results 表：某牌型「被包含」只看对应分组是否存在。
    contains = {"High Card"}
    if five and flush:
        contains.add("Flush Five")
    if three and pairs and flush:
        contains.add("Flush House")
    if five:
        contains.add("Five of a Kind")
    if straight and flush:
        contains.add("Straight Flush")
    if four:
        contains.add("Four of a Kind")
    if three and pairs:
        contains.add("Full House")
    if flush:
        contains.add("Flush")
    if straight:
        contains.add("Straight")
    if three:
        contains.add("Three of a Kind")
    if len(pairs) == 2 or (len(three) == 1 and len(pairs) == 1):
        contains.add("Two Pair")
    if pairs:
        contains.add("Pair")
    # misc_functions.lua:507-517 在最后做一次降级回填：五条补出四条、四条补出三条、
    # 三条补出对子。「含某牌型」的小丑（狡猾、狡诈、机敏、精明、灵巧）据此判定，
    # 所以四条确实「包含对子」——按张数恰好相等去判会漏掉这一层。
    # 回放反例：6BD0552F 第 17 步四条 A，狡猾小丑实际给了 +50 筹码。
    if "Five of a Kind" in contains:
        contains.add("Four of a Kind")
    if "Four of a Kind" in contains:
        contains.add("Three of a Kind")
    if "Three of a Kind" in contains:
        contains.add("Pair")

    if five and flush:
        hand_type, scoring = "Flush Five", list(cards)
    elif three and pairs and flush:
        hand_type, scoring = "Flush House", by_ranks(three[0], pairs[0])
    elif five:
        hand_type, scoring = "Five of a Kind", list(cards)
    elif straight and flush:
        # 游戏取同花的牌，再补上顺子里不在同花中的牌。
        hand_type = "Straight Flush"
        scoring = by_indexes(list(flush_indexes) + list(straight_indexes))
    elif four:
        hand_type, scoring = "Four of a Kind", by_ranks(four[0])
    elif three and pairs:
        hand_type, scoring = "Full House", by_ranks(three[0], pairs[0])
    elif flush:
        hand_type, scoring = "Flush", by_indexes(flush_indexes)
    elif straight:
        hand_type, scoring = "Straight", by_indexes(straight_indexes)
    elif three:
        hand_type, scoring = "Three of a Kind", by_ranks(three[0])
    elif len(pairs) == 2:
        hand_type, scoring = "Two Pair", by_ranks(pairs[0], pairs[1])
    elif pairs:
        hand_type, scoring = "Pair", by_ranks(pairs[0])
    else:
        highest = max(ranks)
        hand_type = "High Card"
        scoring = [next(card for card, (rank, _) in zip(cards, parsed)
                        if rank == highest)]
    return {"hand_type": hand_type, "scoring": scoring, "contains": contains}


def classify_plain_five(cards, jokers=()):
    """返回确认的五张牌型；特殊牌或改变判型的小丑使结果未知。"""
    if len(cards) != 5:
        return None
    result = classify_plain_hand(cards, jokers)
    return result["hand_type"] if result else None


def mouth_locked_type(observation, observed_plays):
    """从本轮已公开的第一手结算推得 The Mouth 锁定的牌型。"""
    boss = (observation.get("blinds") or {}).get("boss") or {}
    round_info = observation.get("round") or {}
    if (boss.get("name") != "The Mouth" or boss.get("status") != "CURRENT" or
            boss.get("disabled") is True or
            not round_info.get("hands_played")):
        return None
    current_round = observation.get("round_num")
    current_ante = observation.get("ante_num")
    for play in observed_plays:
        if (play.get("round") == current_round and play.get("ante") == current_ante and
                isinstance(play.get("hand_type"), str)):
            return play["hand_type"]
    return None


def mouth_play_fact(observation, action, observed_plays):
    """若能确认所选牌型，指出这次出牌是否会被 The Mouth 禁止计分。"""
    locked = mouth_locked_type(observation, observed_plays)
    if locked is None or action.get("method") != "play":
        return None
    indices = (action.get("params") or {}).get("cards")
    hand = (observation.get("hand") or {}).get("cards") or []
    if (not isinstance(indices, list) or len(indices) != 5 or
            any(type(index) is not int or index < 0 or index >= len(hand)
                for index in indices) or len(set(indices)) != 5):
        return None
    actual = classify_plain_five([hand[index] for index in indices],
                                 (observation.get("jokers") or {}).get("cards") or [])
    if actual is None:
        return None
    return {"locked_hand_type": locked, "actual_hand_type": actual,
            "scores_zero_due_to_boss": actual != locked}


def can_make_hand_type(cards, jokers, hand_type, limit=5):
    """手上是否真能凑出指定牌型；用于判断「不许打这手」之外还有没有别的出路。"""
    from itertools import combinations
    usable = [card for card in cards if isinstance(card, dict) and not card.get("hidden")]
    for size in range(1, min(limit, len(usable)) + 1):
        for chosen in combinations(usable, size):
            result = classify_plain_hand(list(chosen), jokers)
            if result and result["hand_type"] == hand_type:
                return True
    return False
