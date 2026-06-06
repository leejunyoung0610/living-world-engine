"""플레이어 자원 스탯 한글 라벨 — API 응답·이벤트 카드용."""

from __future__ import annotations

from typing import Any

DEFAULT_STAT_LABELS_KO: dict[str, str] = {
    "producing": "프로듀싱",
    "rap": "랩",
    "music_skill": "음악 실력",
    "fame": "인지도",
    "inspiration": "영감",
    "hp": "체력",
    "stress": "스트레스",
    "focus": "집중력",
    "mana": "마나",
}


def resolve_stat_label_ko(key: str, world: dict[str, Any] | None = None) -> str:
    """``world.stats_schema.resource[key].label`` 우선, 없으면 기본 매핑, 최종 fallback은 키 자체."""
    if world and isinstance(world, dict):
        schema = world.get("stats_schema")
        if isinstance(schema, dict):
            resource = schema.get("resource")
            if isinstance(resource, dict):
                cfg = resource.get(key)
                if isinstance(cfg, dict):
                    label = cfg.get("label")
                    if label:
                        return str(label)
    return DEFAULT_STAT_LABELS_KO.get(key, key)
