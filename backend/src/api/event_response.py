"""이벤트 발동 결과 — 클라이언트 API 직렬화."""

from __future__ import annotations

from typing import Any

from backend.src.constants.stat_labels import resolve_stat_label_ko


def format_events_for_client(engine: Any, events: list[Any]) -> list[dict[str, Any]]:
    """엔진 내부 ``events_triggered`` 를 API 응답 형태로 변환."""
    world = getattr(getattr(engine, "state", None), "world", None) or {}
    out: list[dict[str, Any]] = []
    for e in events:
        if not isinstance(e, dict):
            continue
        effects_out: list[dict[str, Any]] = []
        for eff in e.get("applied_effects") or []:
            if not isinstance(eff, dict):
                continue
            eff_type = str(eff.get("type", ""))
            if eff_type == "resource_stat":
                key = str(eff.get("key", ""))
                try:
                    delta = int(eff.get("change", 0))
                except (TypeError, ValueError):
                    delta = 0
                effects_out.append({
                    "type": "resource_stat",
                    "key": key,
                    "delta": delta,
                    "before": eff.get("before"),
                    "after": eff.get("after"),
                    "label_ko": resolve_stat_label_ko(key, world),
                })
            elif eff_type == "flag_set":
                effects_out.append({
                    "type": "flag_set",
                    "key": str(eff.get("key", "")),
                    "before": eff.get("before"),
                    "after": eff.get("after"),
                })
        out.append({
            "event_id": str(e.get("event_id", "")),
            "name": str(e.get("name") or e.get("event_id", "")),
            "description": str(e.get("description", "")),
            "narrative_hint": str(e.get("narrative_hint", "")),
            "applied_effects": effects_out,
        })
    return out
