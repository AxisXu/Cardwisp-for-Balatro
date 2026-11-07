"""其他场景的公开事实核对；数值只做能由局面直接确定的运算。"""

import math

from play_scores import build_play_scores
from shop_decision import _slot_status


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _effect_status(card):
    if card.get("description_unresolved"):
        return "uncertain"
    return "known" if isinstance(card.get("description"), str) and card["description"].strip() else "unknown"


def _run_info(snapshot):
    return {"poker_hands": snapshot.get("poker_hands") or {},
            "blind_options": snapshot.get("blind_options") or [],
            "vouchers": snapshot.get("vouchers") or []}


def build_pack_evidence(snapshot):
    """只评估已翻开的卡和仍可选择的次数；不推断未翻开的内容。"""
    pack = snapshot.get("pack") if isinstance(snapshot.get("pack"), dict) else {}
    options = []
    for position, card in enumerate(pack.get("options") or [], 1):
        if not isinstance(card, dict):
            continue
        place = card.get("position", position)
        if card.get("hidden"):
            options.append({"position": place, "hidden": True})
        else:
            options.append({"position": place, "hidden": False, "key": card.get("key"),
                            "name": card.get("name"), "set": card.get("set"),
                            "slot_status": _slot_status(card, snapshot),
                            "effect_status": _effect_status(card),
                            "current_bonus": card.get("current_bonus"),
                            "visible_values": card.get("values") if isinstance(card.get("values"), dict) else None})
    missing = []
    if not isinstance(snapshot.get("pack"), dict):
        missing.append("pack")
    if not _number(pack.get("choices_left")):
        missing.append("choices_left")
    if not options:
        missing.append("visible_pack_options")
    return {"type": pack.get("type"), "choices_left": pack.get("choices_left")
            if _number(pack.get("choices_left")) else None,
            "size": pack.get("size") if _number(pack.get("size")) else None,
            "options": options, "run_info": _run_info(snapshot), "missing": missing}


def build_play_evidence(snapshot):
    """核对目标、剩余次数与可见手牌；不将预览当最终得分。"""
    blind = snapshot.get("blind") if isinstance(snapshot.get("blind"), dict) else {}
    target, scored = blind.get("chips"), blind.get("score")
    needed = max(0, target - scored) if _number(target) and _number(scored) else None
    hand = snapshot.get("hand") if isinstance(snapshot.get("hand"), list) else []
    missing = []
    if needed is None:
        missing.append("blind_target_or_score")
    if not isinstance(snapshot.get("hand"), list):
        missing.append("visible_hand")
    for field in ("hands_left", "discards_left"):
        if not _number(snapshot.get(field)):
            missing.append(field)
    return {"blind_target": target if _number(target) else None,
            "score_so_far": scored if _number(scored) else None,
            "score_needed": needed,
            "hands_left": snapshot.get("hands_left") if _number(snapshot.get("hands_left")) else None,
            "discards_left": snapshot.get("discards_left") if _number(snapshot.get("discards_left")) else None,
            "selected_positions": [index for index, card in enumerate(hand, 1)
                                   if isinstance(card, dict) and card.get("selected")],
            "hidden_hand_cards": sum(1 for card in hand if isinstance(card, dict) and card.get("hidden")),
            "current_hand_preview": snapshot.get("current_hand"),
            "verified_play_scores": build_play_scores(snapshot, needed),
            "run_info": _run_info(snapshot), "missing": missing}


def build_blind_evidence(snapshot):
    """只比较比赛信息中当前可见的盲注和跳过标签。"""
    options = snapshot.get("blind_options") if isinstance(snapshot.get("blind_options"), list) else []
    visible = [{key: option.get(key) for key in
                ("slot", "key", "name", "state", "chips", "reward", "effect",
                 "effect_unresolved", "skip_tag", "skip_tag_effect", "skip_tag_effect_unresolved")
                if key in option}
               for option in options if isinstance(option, dict) and not option.get("hidden")]
    return {"on_deck": snapshot.get("blind_on_deck"), "visible_options": visible,
            "boss_reroll": {"cost": snapshot.get("boss_reroll_cost"),
                            "available": snapshot.get("boss_reroll_available")},
            "run_info": _run_info(snapshot),
            "missing": [] if visible else ["visible_blind_options"]}
