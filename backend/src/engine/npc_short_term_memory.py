"""NPC별 세션 단기기억 — 대화 맥락·관계 변화 개연성용."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)

MAX_ENTRIES_PER_NPC = 6
DEFAULT_TTL_TURNS = 8
MAX_UPDATES_PER_TURN = 3


class NpcShortTermMemory:
    """플레이 세션 동안 NPC별 최근 기억 큐 (npc_id → entries)."""

    def __init__(self) -> None:
        self.by_npc: dict[str, list[dict[str, Any]]] = {}

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return deepcopy(self.by_npc)

    def load_from_dict(self, data: dict[str, Any] | None) -> None:
        if not isinstance(data, dict):
            self.by_npc = {}
            return
        out: dict[str, list[dict[str, Any]]] = {}
        for npc_id, entries in data.items():
            if not isinstance(entries, list):
                continue
            cleaned = [e for e in entries if isinstance(e, dict) and e.get("summary")]
            if cleaned:
                out[str(npc_id)] = cleaned
        self.by_npc = out

    def prune(self, current_turn: int) -> None:
        """TTL 지난 항목 제거."""
        for npc_id in list(self.by_npc.keys()):
            kept = [
                e
                for e in self.by_npc[npc_id]
                if int(e.get("turn", 0)) + int(e.get("ttl_turns", DEFAULT_TTL_TURNS)) > current_turn
            ]
            if kept:
                self.by_npc[npc_id] = kept[-MAX_ENTRIES_PER_NPC:]
            else:
                del self.by_npc[npc_id]

    def add_entry(
        self,
        npc_id: str,
        *,
        turn: int,
        summary: str,
        emotion: str = "neutral",
        ttl_turns: int = DEFAULT_TTL_TURNS,
    ) -> None:
        summary = summary.strip()
        if not npc_id or not summary:
            return
        entry = {
            "turn": turn,
            "summary": summary,
            "emotion": emotion,
            "ttl_turns": ttl_turns,
        }
        bucket = self.by_npc.setdefault(npc_id, [])
        bucket.append(entry)
        self.by_npc[npc_id] = bucket[-MAX_ENTRIES_PER_NPC:]

    def apply_updates(
        self,
        updates: list[dict[str, Any]],
        *,
        resolve_npc_id: Any,
        turn: int,
    ) -> list[dict[str, Any]]:
        """검증된 ``npc_memory_updates`` 적용. ``resolve_npc_id(character) -> npc_id | None``."""
        applied: list[dict[str, Any]] = []
        for upd in updates[:MAX_UPDATES_PER_TURN]:
            if not isinstance(upd, dict):
                continue
            character = str(upd.get("character", "")).strip()
            summary = str(upd.get("summary", "")).strip()
            if not character or len(summary) < 4:
                continue
            npc_id = resolve_npc_id(character)
            if not npc_id:
                continue
            emotion = str(upd.get("emotion", "neutral")).strip() or "neutral"
            self.add_entry(npc_id, turn=turn, summary=summary, emotion=emotion)
            applied.append({
                "character": character,
                "npc_id": npc_id,
                "summary": summary,
                "emotion": emotion,
            })
            logger.info("NPC 단기기억 +%s: %s", character, summary[:60])
        return applied

    def format_for_prompt(
        self,
        npcs: list[dict[str, Any]],
        *,
        active_npc_ids: set[str] | None = None,
        current_turn: int = 0,
    ) -> str:
        """dynamic 프롬프트용 Markdown 블록."""
        self.prune(current_turn)
        id_to_name = {
            str(n.get("id", "")): str(n.get("name", "")).strip()
            for n in npcs
            if n.get("id")
        }
        lines: list[str] = []
        for npc_id, entries in self.by_npc.items():
            if active_npc_ids is not None and npc_id not in active_npc_ids:
                continue
            name = id_to_name.get(npc_id, npc_id)
            if not entries:
                continue
            lines.append(f"### {name}")
            for e in entries[-MAX_ENTRIES_PER_NPC:]:
                t = e.get("turn", "?")
                lines.append(f"- [턴 {t}] {e.get('summary', '')}")
        if not lines:
            return "(없음 — 이번 턴 상호작용 후 `npc_memory_updates`로 갱신)"
        return "\n".join(lines)
