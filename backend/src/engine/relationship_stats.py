"""플레이어↔NPC 관계 수치 — 플랫폼 고정 8종 (0–100, 턴당 LLM 변동)."""

from __future__ import annotations

from typing import Final

# 순서: UI·프롬프트 표시용
RELATIONSHIP_STAT_ORDER: Final[tuple[str, ...]] = (
    "affection",
    "trust",
    "respect",
    "fear",
    "loyalty",
    "romance",
    "disgust",
    "wrath",
)

RELATIONSHIP_STAT_LABELS_KO: Final[dict[str, str]] = {
    "affection": "호감",
    "trust": "신뢰",
    "respect": "존경",
    "fear": "두려움",
    "loyalty": "충성",
    "romance": "로맨스",
    "disgust": "혐오",
    "wrath": "살의",
}

VALID_RELATIONSHIP_STATS: Final[frozenset[str]] = frozenset(RELATIONSHIP_STAT_ORDER)

DEFAULT_RELATIONSHIP_STAT_VALUE: Final[int] = 50

# UI에서 스탯 추가 시 권장 초기값
RELATIONSHIP_STAT_DEFAULT_ON_ADD: Final[dict[str, int]] = {
    "affection": 50,
    "trust": 50,
    "respect": 50,
    "fear": 50,
    "loyalty": 50,
    "romance": 0,
    "disgust": 0,
    "wrath": 0,
}


def normalize_relationship_stat_values(raw: object) -> dict[str, int]:
    """플랫폼 8종만 0–100 정수로 정규화."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, val in raw.items():
        if key not in VALID_RELATIONSHIP_STATS:
            continue
        try:
            n = int(val)
        except (TypeError, ValueError):
            continue
        out[key] = max(0, min(100, n))
    return out


def npc_relationship_profile(npc: dict[str, object]) -> dict[str, int]:
    """NPC에 설정된 관계 스탯(키=활성, 값=초기값). 없으면 빈 dict."""
    rs = npc.get("relationship_stats")
    if isinstance(rs, dict) and rs:
        return normalize_relationship_stat_values(rs)
    legacy = npc.get("initial_stats")
    if isinstance(legacy, dict) and legacy:
        return normalize_relationship_stat_values(legacy)
    return {}


def npc_allows_relationship_stat(npc: dict[str, object], stat: str) -> bool:
    profile = npc_relationship_profile(npc)
    return bool(profile) and stat in profile


def seed_player_relationships_from_npcs(
    player: dict[str, object],
    npcs: list[dict[str, object]],
) -> None:
    """플레이 시작 시 NPC ``relationship_stats`` 로 ``player.relationships`` 시드."""
    rel = player.get("relationships")
    if not isinstance(rel, dict):
        rel = {}
    for npc in npcs:
        nid = npc.get("id")
        if not isinstance(nid, str) or not nid.strip():
            continue
        profile = npc_relationship_profile(npc)
        if not profile:
            continue
        existing = rel.get(nid)
        if isinstance(existing, dict) and existing:
            rel[nid] = {
                k: max(0, min(100, int(existing.get(k, profile[k]))))
                if isinstance(existing.get(k), (int, float))
                else profile[k]
                for k in profile
            }
        else:
            rel[nid] = dict(profile)
    player["relationships"] = rel


def build_session_relationship_view(
    npcs: list[dict[str, object]],
    player: dict[str, object],
) -> list[dict[str, object]]:
    """플레이 UI용 — NPC별 활성 스탯과 현재값만."""
    rel = player.get("relationships")
    if not isinstance(rel, dict):
        rel = {}
    rows: list[dict[str, object]] = []
    for npc in npcs:
        nid = npc.get("id")
        name = npc.get("name")
        if not isinstance(nid, str) or not nid.strip():
            continue
        profile = npc_relationship_profile(npc)
        if not profile:
            continue
        current = rel.get(nid)
        if not isinstance(current, dict):
            current = {}
        stats = {
            k: max(0, min(100, int(current.get(k, profile[k]))))
            if isinstance(current.get(k), (int, float))
            else profile[k]
            for k in profile
        }
        rows.append(
            {
                "npc_id": nid,
                "npc_name": str(name) if name else nid,
                "stats": stats,
            }
        )
    return rows
