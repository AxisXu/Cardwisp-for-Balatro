"""出牌阶段的精确计分：把插件快照转成计分器（hand_score）要的格式，列出能确定得分的出牌。

计分器只在公开信息足以确定时给数，否则不列；所以这里列出的是「已核实的最终得分」，
没列出的组合不代表分低。2026-11-03 对照实验：模型照着它出牌时思考少 38%（回答更快），
胜负与不给分时持平；22 手可核对的出牌全部与实际结算一致。
"""

from itertools import combinations

from hand_score import score_plain_play

RANKS = {"Ace": "A", "King": "K", "Queen": "Q", "Jack": "J", "10": "T"}
SUITS = {"Spades": "S", "Hearts": "H", "Diamonds": "D", "Clubs": "C"}
MAX_PLAYED = 5
TOP_PLAYS = 5


def _modifier(card, joker=False):
    """与 balatrobot 的 modifier 同口径：大写的蜡封、版本、增强，以及非零的计分字段。"""
    modifier = {}
    if card.get("seal"):
        modifier["seal"] = str(card["seal"]).upper()
    if card.get("edition"):
        modifier["edition"] = str(card["edition"]).upper()
    if card.get("enhancement"):
        modifier["enhancement"] = str(card["enhancement"]).replace(" Card", "").upper()
    values = card.get("values") if isinstance(card.get("values"), dict) else {}
    for field in ("bonus", "perma_bonus"):
        if type(values.get(field)) in (int, float) and values[field] != 0:
            modifier[field] = values[field]
    if not joker:
        if type(values.get("mult")) in (int, float) and values["mult"] != 0:
            modifier["mult"] = values["mult"]
        if type(values.get("x_mult")) in (int, float) and values["x_mult"] > 1:
            modifier["x_mult"] = values["x_mult"]
    return modifier


def _playing_card(card):
    rank, suit = RANKS.get(str(card.get("rank")), str(card.get("rank"))), SUITS.get(card.get("suit"))
    if not suit or rank not in ("A", "K", "Q", "J", "T", "2", "3", "4", "5", "6", "7", "8", "9"):
        return None
    result = {"key": suit + "_" + rank, "set": "ENHANCED" if card.get("enhancement") else "DEFAULT",
              "label": card.get("name") or "", "value": {"rank": rank, "suit": suit,
                                                         "effect": card.get("description") or ""},
              "modifier": _modifier(card)}
    if card.get("debuffed"):
        result["state"] = {"debuff": True}
    return result


def _joker(card):
    result = {"key": card.get("key"), "set": "JOKER", "label": card.get("name") or "",
              "rarity": card.get("rarity"), "rarity_label": card.get("rarity_label"),
              "value": {"effect": card.get("description") or ""},
              "modifier": _modifier(card, joker=True), "cost": {"sell": card.get("sell_cost")}}
    values = card.get("values") if isinstance(card.get("values"), dict) else {}
    if card.get("key") == "j_misprint" and all(type(values.get(field)) in (int, float)
                                                for field in ("extra_min", "extra_max")):
        # 误打误撞的公开范围（卡面滚动的 +0~23）：balatrobot 叫 random_mult_min/max。
        result["value"].update(random_mult_min=values["extra_min"], random_mult_max=values["extra_max"])
    if isinstance(card.get("current_bonus"), dict):
        result["current_bonus"] = card["current_bonus"]
    if card.get("debuffed"):
        result["state"] = {"debuff": True}
    return result


def build_play_scores(snapshot, score_needed):
    """返回能确定得分的前几种出牌（按保证得分从高到低）；有背面手牌或算不出任何组合时返回 None。"""
    hand = snapshot.get("hand") if isinstance(snapshot.get("hand"), list) else []
    if not hand or any(not isinstance(card, dict) or card.get("hidden") for card in hand):
        return None
    cards = [_playing_card(card) for card in hand]
    if any(card is None for card in cards):
        return None
    owned = [card for card in snapshot.get("owned") or [] if isinstance(card, dict)]
    if any(card.get("hidden") for card in owned):
        return None
    jokers = [_joker(card) for card in owned]
    blind = snapshot.get("blind") if isinstance(snapshot.get("blind"), dict) else {}
    blinds = {"current": {"key": blind.get("key"), "name": blind.get("name"), "effect": blind.get("effect") or "",
                          "status": "CURRENT", "disabled": blind.get("disabled") is True,
                          "score": blind.get("chips")}}
    round_state = {field: snapshot.get(field) for field in
                   ("hands_left", "discards_left", "hands_played", "discards_used", "money")
                   if type(snapshot.get(field)) in (int, float)}
    round_state["chips"] = blind.get("score")
    if type(snapshot.get("slots")) is int:
        round_state["joker_limit"] = snapshot["slots"]
    round_state["joker_count"] = len(jokers)
    poker_hands = snapshot.get("poker_hands") if isinstance(snapshot.get("poker_hands"), dict) else {}
    scored = []
    for size in range(1, min(MAX_PLAYED, len(cards)) + 1):
        for picked in combinations(range(len(cards)), size):
            chosen = set(picked)
            result = score_plain_play([cards[index] for index in picked], jokers, poker_hands,
                                      round_state, blinds,
                                      held_cards=[card for index, card in enumerate(cards) if index not in chosen])
            if not result:
                continue
            row = {"positions": [index + 1 for index in picked],
                   "cards": [hand[index].get("name") for index in picked],
                   "hand_type": result["hand_type"]}
            if result["score_min"] == result["score_max"]:
                row["score"] = result["score_min"]
            else:
                row["score_min"], row["score_max"] = result["score_min"], result["score_max"]
            scored.append((result["score_min"], result["score_max"], picked, row))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[2]))
    best_min = scored[0][0]
    best_max = max(item[1] for item in scored)
    result = {"top_plays": [item[3] for item in scored[:TOP_PLAYS]],
              "best_guaranteed_score": best_min,
              "unlisted_plays_are_unverified_not_lower": True}
    if type(score_needed) in (int, float):
        result["best_clears_score_needed"] = best_min >= score_needed
        result["no_listed_play_can_clear"] = best_max < score_needed
    return result
