"""商店公开局面的确定性核对。"""

import math


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _interest(balance, economy):
    if economy.get("no_interest") is True:
        return 0
    amount = economy.get("interest_per_5")
    cap = economy.get("interest_cap")
    if (economy.get("no_interest") is not False or not _number(balance)
            or not _number(amount) or not _number(cap) or amount < 0 or cap < 0):
        return None
    return amount * min(math.floor(max(0, balance) / 5), cap / 5)


def _transaction(price, money, bankrupt_at, economy, interest_now, free_allowed=False):
    balance = money - price if _number(money) and _number(price) else None
    after = _interest(balance, economy)
    affordable = (True if free_allowed and _number(price) and price <= 0 else
                  balance >= bankrupt_at if _number(balance) and _number(bankrupt_at) else None)
    return {
        "affordable": affordable,
        "balance_after_direct_cost": balance,
        "interest_if_balance_unchanged": after,
        "interest_change_if_balance_unchanged": (
            after - interest_now if _number(after) and _number(interest_now) else None),
    }


def _slot_status(item, snapshot):
    kind = item.get("set")
    negative_space = 1 if item.get("edition") == "negative" else 0
    if kind == "Joker":
        used, limit = snapshot.get("jokers"), snapshot.get("slots")
    elif kind in ("Tarot", "Planet", "Spectral"):
        held, limit = snapshot.get("consumables"), snapshot.get("consumable_slots")
        used = len(held) if isinstance(held, list) else None
    elif kind in ("Booster", "Voucher", "Default", "Enhanced"):
        return "not_applicable"
    else:
        return "unknown"
    if not _number(used) or not _number(limit):
        return "unknown"
    return "full" if used >= limit + negative_space else "available"


def _swap_options(item, snapshot, price, money, bankrupt_at, economy, current_interest, missing):
    """列出普通可出售小丑腾位后购买该商品的直接账目。"""
    if item.get("set") != "Joker" or _slot_status(item, snapshot) != "full":
        return []
    owned = snapshot.get("owned")
    if not isinstance(owned, list):
        missing.append("owned_jokers")
        return []
    options = []
    for index, card in enumerate(owned, 1):
        if not isinstance(card, dict) or card.get("set") != "Joker":
            continue
        # 永恒牌不能出售；出售负片牌会同时移除其额外槽位，不能据此断定腾出了位置。
        if card.get("eternal") or card.get("edition") == "negative":
            continue
        proceeds = card.get("sell_cost")
        if not _number(proceeds):
            missing.append("owned_joker_sell_cost_" + str(index))
            continue
        exchange = _transaction(price - proceeds if _number(price) else None,
                                money, bankrupt_at, economy, current_interest)
        options.append({"sell_position": card.get("position", index),
                        "sell_key": card.get("key"), "sell_name": card.get("name"),
                        "sell_proceeds": proceeds,
                        "balance_after_direct_exchange": exchange["balance_after_direct_cost"],
                        "affordable": exchange["affordable"],
                        "interest_if_balance_unchanged": exchange["interest_if_balance_unchanged"],
                        "interest_change_if_balance_unchanged":
                            exchange["interest_change_if_balance_unchanged"]})
    return options


def _baseball_synergy(snapshot):
    owned = snapshot.get("owned")
    if not isinstance(owned, list):
        return None
    baseball_cards = [card for card in owned if isinstance(card, dict) and
                      card.get("key") == "j_baseball"]
    # 多张棒球卡的合并收益不能用单张公式表示；保留未知而不报错数。
    if len(baseball_cards) != 1:
        return None
    baseball = baseball_cards[0]
    values = baseball.get("values") or {}
    multiplier = values.get("extra") if isinstance(values, dict) else None
    if not _number(multiplier) or multiplier <= 0:
        return None
    uncommon = []
    unknown = []
    for index, card in enumerate(owned, 1):
        if not isinstance(card, dict) or card.get("set") != "Joker" or \
                card.get("key") == "j_baseball":
            continue
        position = card.get("position", index)
        rarity = card.get("rarity_label")
        if rarity == "UNCOMMON":
            uncommon.append(position)
        elif rarity not in ("COMMON", "RARE", "LEGENDARY"):
            unknown.append(position)
    return {"per_uncommon_x_mult": multiplier,
            "confirmed_uncommon_positions": uncommon,
            "unknown_rarity_positions": unknown,
            "confirmed_x_mult": multiplier ** len(uncommon)}


def build_shop_evidence(snapshot, shop_state_version):
    """为本次商店提问计算可验证的购买与重掷事实；未知值保持 null。"""
    economy = snapshot.get("economy") if isinstance(snapshot.get("economy"), dict) else {}
    money = snapshot.get("money")
    bankrupt_at = economy.get("bankrupt_at")
    current_interest = _interest(money, economy)
    missing = []
    if not _number(money):
        missing.append("money")
    if not _number(bankrupt_at):
        missing.append("bankrupt_at")
    if current_interest is None:
        missing.append("interest_rules")

    free = economy.get("free_rerolls")
    reroll_price = economy.get("reroll_cost")
    cost_now = reroll_price if _number(reroll_price) else None
    if cost_now is None:
        missing.append("reroll_cost")
    reroll = {"cost_now": cost_now, "free_rerolls": free if _number(free) else None,
              **_transaction(cost_now, money, bankrupt_at, economy, current_interest,
                             free_allowed=True)}

    offers = []
    shop = snapshot.get("shop")
    if not isinstance(shop, list) or not shop:
        missing.append("visible_shop_items")
    for position, item in enumerate(shop if isinstance(shop, list) else [], 1):
        if not isinstance(item, dict):
            continue
        price = item.get("cost") if _number(item.get("cost")) else None
        if price is None:
            missing.append("offer_price_" + str(position))
        description = item.get("description")
        effect = ("uncertain" if item.get("description_unresolved") else
                  "known" if isinstance(description, str) and description.strip() else "unknown")
        offers.append({"position": position, "key": item.get("key"), "name": item.get("name"),
                       "set": item.get("set"), "price": price,
                       **_transaction(price, money, bankrupt_at, economy, current_interest,
                                      free_allowed=item.get("set") in
                                      ("Joker", "Tarot", "Planet", "Spectral", "Booster", "Default", "Enhanced")),
                       "slot_status": _slot_status(item, snapshot),
                       "effect_status": effect, "current_bonus": item.get("current_bonus"),
                       "visible_values": item.get("values") if isinstance(item.get("values"), dict) else None,
                       "contents_status": "unopened_unknown" if item.get("set") == "Booster" else None,
                       "swap_options": _swap_options(item, snapshot, price, money, bankrupt_at,
                                                     economy, current_interest, missing)})

    result = {"shop_state_version": shop_state_version, "money": money if _number(money) else None,
            "interest_at_current_balance": current_interest,
            "offers": offers, "reroll": reroll, "missing": missing}
    baseball = _baseball_synergy(snapshot)
    if baseball is not None:
        result["baseball_synergy"] = baseball
    return result
