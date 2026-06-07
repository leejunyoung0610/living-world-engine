"""LLM `resource_stat_changes` → EventCard용 `events_triggered` 합성."""

from __future__ import annotations

from typing import Any

# 턴당 스탯 1건 최대 변화량 (validator와 동기화)
MAX_RESOURCE_STAT_CHANGE = 5
# 카드 표시 최소 절대 변화량 (`show_card` 없을 때)
MIN_CARD_ABS_DELTA = 3


def build_llm_stat_event(
    turn: int,
    resource_changes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """적용된 자원 스탯 변화를 마일스톤과 동일한 `events_triggered` 항목 1개로 합성."""
    effects: list[dict[str, Any]] = []
    reasons: list[str] = []
    for ch in resource_changes:
        if not isinstance(ch, dict):
            continue
        key = str(ch.get("key", "")).strip()
        if not key:
            continue
        try:
            delta = int(ch.get("change", 0))
        except (TypeError, ValueError):
            continue
        if delta == 0:
            continue
        show = bool(ch.get("show_card"))
        if not show and abs(delta) < MIN_CARD_ABS_DELTA:
            continue
        effects.append({
            "type": "resource_stat",
            "key": key,
            "change": delta,
            "before": ch.get("before"),
            "after": ch.get("after"),
        })
        reason = str(ch.get("reason", "")).strip()
        if reason:
            reasons.append(reason)

    if not effects:
        return None

    description = reasons[0] if len(reasons) == 1 else " · ".join(reasons[:2])
    if not description:
        description = "능력에 변화가 생겼다."

    return {
        "event_id": f"llm_stat_turn_{turn}",
        "name": "능력 변화",
        "description": description,
        "narrative_hint": "",
        "applied_effects": effects,
    }
