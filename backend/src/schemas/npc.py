"""UGC NPC Canonical 스키마 — 저장 시 정규화·최소 검증."""

from __future__ import annotations

import re
from typing import Any

_NPC_ID_FALLBACK = re.compile(r"[^a-z0-9_-]+")

MAJOR_MAX_LEN = 120
PERSONALITY_MAX_LEN = 500
BACKGROUND_MAX_LEN = 2000
SPEAKING_STYLE_STR_MAX_LEN = 200
APPEARANCE_FOR_AI_MAX_LEN = 800

_PRESERVE_KEYS = (
    "location",
    "portrait_image_url",
    "persona",
    "skills",
    "interests",
    "age",
    "initial_stats",
    "description",
)


def _slugify_npc_id(name: str, index: int) -> str:
    base = name.strip().lower().replace(" ", "_")
    base = _NPC_ID_FALLBACK.sub("_", base).strip("_")[:96]
    return base or f"npc_{index + 1}"


def _trim_optional_str(raw: dict[str, Any], key: str, *, max_len: int) -> str | None:
    v = raw.get(key)
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def _speaking_style_value(raw: dict[str, Any]) -> str | dict[str, Any] | None:
    if "speaking_style" in raw:
        v = raw["speaking_style"]
    elif "speech_style" in raw:
        v = raw["speech_style"]
    else:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if len(s) > SPEAKING_STYLE_STR_MAX_LEN:
            s = s[: SPEAKING_STYLE_STR_MAX_LEN - 1] + "…"
        return s
    if isinstance(v, dict) and v:
        return v
    return None


def normalize_npc_record(raw: Any, index: int) -> dict[str, Any]:
    """단일 NPC dict 정규화. 실패 시 ValueError."""
    if not isinstance(raw, dict):
        raise ValueError(f"npcs[{index}] must be an object")

    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"npcs[{index}].name is required")

    npc_id = str(raw.get("id", "")).strip() or _slugify_npc_id(name, index)
    role = str(raw.get("role", "")).strip() or "등장인물"

    out: dict[str, Any] = {"id": npc_id, "name": name, "role": role}

    for key, max_len in (
        ("major", MAJOR_MAX_LEN),
        ("personality", PERSONALITY_MAX_LEN),
        ("background", BACKGROUND_MAX_LEN),
        ("appearance_for_ai", APPEARANCE_FOR_AI_MAX_LEN),
    ):
        s = _trim_optional_str(raw, key, max_len=max_len)
        if s:
            out[key] = s

    style = _speaking_style_value(raw)
    if style is not None:
        out["speaking_style"] = style

    for key in _PRESERVE_KEYS:
        if key in raw and raw[key] is not None:
            out[key] = raw[key]

    return out


def normalize_characters_for_storage(characters: dict[str, Any]) -> dict[str, Any]:
    """UGC characters payload — npcs 정규화, player 제거, quests 보존."""
    npcs_raw = characters.get("npcs")
    if not isinstance(npcs_raw, list):
        npcs_raw = []

    npcs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(npcs_raw):
        n = normalize_npc_record(raw, i)
        nid = str(n["id"])
        if nid in seen_ids:
            nid = f"{nid}_{i + 1}"
            n["id"] = nid
        seen_ids.add(nid)
        npcs.append(n)

    out: dict[str, Any] = {"npcs": npcs}
    q = characters.get("quests")
    if isinstance(q, list):
        out["quests"] = q
    return out
