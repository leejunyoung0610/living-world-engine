"""
StateChangeValidator - LLM 상태 변경 검증

LLM이 제안한 상태 변경을 검증하고 안전한 범위 내로 제한합니다.
게임 밸런스를 유지하는 핵심 모듈입니다.

TODO: Week 1 Day 3-4에 구현 완성
"""

from __future__ import annotations

from typing import Any

from ..utils.logger import logger
from .relationship_stats import VALID_RELATIONSHIP_STATS

MAX_RELATIONSHIP_CHANGES_PER_TURN = 2
MAX_RELATIONSHIP_CHANGE_SUM_ABS = 5
MIN_RELATIONSHIP_REASON_LEN = 4


class StateChangeValidator:
    """LLM이 제안한 상태 변경을 검증"""

    def __init__(self, valid_characters: list[str] | None = None) -> None:
        self.valid_characters = valid_characters or []
        self.max_relationship_change = 3  # 1건당 최대 변화량
        self.max_resource_stat_change = 5
        self.valid_stats = set(VALID_RELATIONSHIP_STATS)
        self.valid_resource_stats: set[str] = set()

    def set_valid_characters(self, characters: list[str]) -> None:
        """유효한 캐릭터 목록 설정"""
        self.valid_characters = characters

    def set_valid_resource_stats(self, keys: list[str] | set[str]) -> None:
        """플레이어 자원 스탯 허용 키 (`stats_schema.resource` + 현재 player.stats)."""
        self.valid_resource_stats = {str(k).strip() for k in keys if str(k).strip()}

    def validate(self, changes: dict[str, Any]) -> dict[str, Any]:
        """검증 후 안전한 변경만 반환"""
        validated: dict[str, Any] = {}

        if "relationship_changes" in changes:
            validated["relationship_changes"] = self._validate_relationship_changes(
                changes["relationship_changes"]
            )

        if "resource_stat_changes" in changes:
            validated["resource_stat_changes"] = []
            for rc in changes["resource_stat_changes"]:
                validated_rc = self._validate_resource_stat_change(rc)
                if validated_rc is not None:
                    validated["resource_stat_changes"].append(validated_rc)

        if "new_memories" in changes:
            validated["new_memories"] = []
            for mem in changes["new_memories"]:
                validated_mem = self._validate_memory(mem)
                if validated_mem is not None:
                    validated["new_memories"].append(validated_mem)

        if "npc_memory_updates" in changes:
            validated["npc_memory_updates"] = self._validate_npc_memory_updates(
                changes["npc_memory_updates"]
            )

        return validated

    def _validate_relationship_changes(self, raw: Any) -> list[dict[str, Any]]:
        """관계 변경 목록 — 건수·합계 캡 적용."""
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for rc in raw[:MAX_RELATIONSHIP_CHANGES_PER_TURN]:
            validated_rc = self._validate_relationship_change(rc)
            if validated_rc is not None:
                out.append(validated_rc)
        # 턴당 절대값 합계 캡
        total_abs = sum(abs(x["change"]) for x in out)
        while out and total_abs > MAX_RELATIONSHIP_CHANGE_SUM_ABS:
            dropped = out.pop()
            total_abs -= abs(dropped["change"])
            logger.info(
                "관계 변화 합계 캡: %s %s 제거",
                dropped.get("character"),
                dropped.get("stat"),
            )
        return out

    def _validate_relationship_change(self, change: dict[str, Any]) -> dict[str, Any] | None:
        """관계 변경 검증 — 개연성 ``reason`` 필수."""
        character = change.get("character", "")
        stat = change.get("stat", "")
        amount = change.get("change", 0)
        reason = str(change.get("reason", "")).strip()

        if self.valid_characters and character not in self.valid_characters:
            logger.warning(f"존재하지 않는 캐릭터: {character}")
            return None

        if stat not in self.valid_stats:
            logger.warning(f"유효하지 않은 관계 스탯: {stat}")
            return None

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return None

        if amount == 0:
            return None

        if len(reason) < MIN_RELATIONSHIP_REASON_LEN:
            logger.warning("관계 변화 거부 — reason 부족: %s", character)
            return None

        clamped = max(-self.max_relationship_change, min(self.max_relationship_change, amount))
        if clamped != amount:
            logger.info(f"관계 변화량 제한: {amount} → {clamped}")

        return {
            "character": character,
            "stat": stat,
            "change": clamped,
            "reason": reason,
        }

    def _validate_resource_stat_change(self, change: dict[str, Any]) -> dict[str, Any] | None:
        key = str(change.get("key", "")).strip()
        if not key:
            return None
        if self.valid_resource_stats and key not in self.valid_resource_stats:
            logger.warning("유효하지 않은 자원 스탯 키: %s", key)
            return None
        try:
            amount = int(change.get("change", 0))
        except (TypeError, ValueError):
            return None
        if amount == 0:
            return None
        clamped = max(
            -self.max_resource_stat_change,
            min(self.max_resource_stat_change, amount),
        )
        if clamped != amount:
            logger.info("자원 스탯 변화량 제한: %s %s → %s", key, amount, clamped)
        out: dict[str, Any] = {
            "key": key,
            "change": clamped,
            "reason": str(change.get("reason", "")).strip(),
        }
        if "show_card" in change:
            out["show_card"] = bool(change["show_card"])
        return out

    def _validate_npc_memory_updates(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        from .npc_short_term_memory import MAX_UPDATES_PER_TURN

        out: list[dict[str, Any]] = []
        seen_chars: set[str] = set()
        for upd in raw[:MAX_UPDATES_PER_TURN]:
            if not isinstance(upd, dict):
                continue
            character = str(upd.get("character", "")).strip()
            summary = str(upd.get("summary", "")).strip()
            if not character or len(summary) < 4:
                continue
            if self.valid_characters and character not in self.valid_characters:
                continue
            if character in seen_chars:
                continue
            seen_chars.add(character)
            emotion = str(upd.get("emotion", "neutral")).strip() or "neutral"
            valid_emotions = {"joy", "sadness", "anger", "fear", "surprise", "trust", "neutral"}
            if emotion not in valid_emotions:
                emotion = "neutral"
            out.append({
                "character": character,
                "summary": summary,
                "emotion": emotion,
            })
        return out

    def _validate_memory(self, memory: dict[str, Any]) -> dict[str, Any] | None:
        """기억 검증"""
        content = memory.get("content", "")
        if not content or len(content) < 2:
            logger.warning("빈 기억 무시")
            return None

        importance = memory.get("importance", 5)
        importance = max(1, min(10, importance))  # 1-10 범위 제한

        valid_emotions = {"joy", "sadness", "anger", "fear", "surprise", "trust", "neutral"}
        emotion = memory.get("emotion", "neutral")
        if emotion not in valid_emotions:
            emotion = "neutral"

        return {
            "content": content,
            "emotion": emotion,
            "importance": importance,
        }
