"""
StateChangeValidator - LLM 상태 변경 검증

LLM이 제안한 상태 변경을 검증하고 안전한 범위 내로 제한합니다.
게임 밸런스를 유지하는 핵심 모듈입니다.

TODO: Week 1 Day 3-4에 구현 완성
"""

from __future__ import annotations

from typing import Any

from backend.src.utils.logger import logger


class StateChangeValidator:
    """LLM이 제안한 상태 변경을 검증"""

    def __init__(self, valid_characters: list[str] | None = None) -> None:
        self.valid_characters = valid_characters or []
        self.max_relationship_change = 10  # 한 턴당 최대 변화량
        self.valid_stats = {"affection", "trust", "respect", "fear"}

    def set_valid_characters(self, characters: list[str]) -> None:
        """유효한 캐릭터 목록 설정"""
        self.valid_characters = characters

    def validate(self, changes: dict[str, Any]) -> dict[str, Any]:
        """검증 후 안전한 변경만 반환"""
        validated: dict[str, Any] = {}

        # 관계 변경 검증
        if "relationship_changes" in changes:
            validated["relationship_changes"] = []
            for rc in changes["relationship_changes"]:
                validated_rc = self._validate_relationship_change(rc)
                if validated_rc is not None:
                    validated["relationship_changes"].append(validated_rc)

        # 새 기억 검증
        if "new_memories" in changes:
            validated["new_memories"] = []
            for mem in changes["new_memories"]:
                validated_mem = self._validate_memory(mem)
                if validated_mem is not None:
                    validated["new_memories"].append(validated_mem)

        return validated

    def _validate_relationship_change(self, change: dict[str, Any]) -> dict[str, Any] | None:
        """관계 변경 검증"""
        character = change.get("character", "")
        stat = change.get("stat", "")
        amount = change.get("change", 0)

        # 캐릭터 존재 확인
        if self.valid_characters and character not in self.valid_characters:
            logger.warning(f"존재하지 않는 캐릭터: {character}")
            return None

        # 유효한 스탯인지 확인
        if stat not in self.valid_stats:
            logger.warning(f"유효하지 않은 관계 스탯: {stat}")
            return None

        # 변화량 제한 (-10 ~ +10)
        clamped = max(-self.max_relationship_change, min(self.max_relationship_change, amount))
        if clamped != amount:
            logger.info(f"관계 변화량 제한: {amount} → {clamped}")

        return {
            "character": character,
            "stat": stat,
            "change": clamped,
            "reason": change.get("reason", ""),
        }

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
