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
from .story_facts import (
    MAX_FLAG_CHANGES_PER_TURN,
    MIN_FLAG_REASON_LEN,
    normalize_flag_key,
    normalize_flag_value,
)

MAX_RELATIONSHIP_CHANGES_PER_TURN = 2
MAX_RELATIONSHIP_CHANGE_SUM_ABS = 5
MIN_RELATIONSHIP_REASON_LEN = 4
DEFAULT_MEMORY_IMPORTANCE = 5
VALID_EMOTIONS = frozenset({"joy", "sadness", "anger", "fear", "surprise", "trust", "neutral"})


def _coerce_int(value: Any) -> int | None:
    """LLM 툴 입력의 수치를 정수로. int·유한 float·숫자 문자열(\"7\", \"-2.0\")만 허용.

    float 는 기존 ``int()`` 와 같이 0 방향으로 버림. bool·None·리스트 등은 None (거부).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    if isinstance(value, (float, str)):
        try:
            return int(float(value))
        except (ValueError, OverflowError):  # 'abc', nan, inf
            return None
    return None


def _text(value: Any) -> str:
    """문자열 필드 — 문자열이 아니면 빈 문자열(검증 실패로 이어짐)."""
    return value.strip() if isinstance(value, str) else ""


def _as_list(raw: Any, field: str) -> list[Any]:
    """배열 필드 — 리스트가 아니면 경고 후 빈 리스트 (문자열을 글자 단위로 순회하는 사고 방지)."""
    if isinstance(raw, list):
        return raw
    if raw is not None:
        logger.warning("%s 형식 오류 — 배열 아님(%s), 무시", field, type(raw).__name__)
    return []


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
        """검증 후 안전한 변경만 반환 — 형식이 틀린 항목은 버리고 예외를 던지지 않는다."""
        validated: dict[str, Any] = {}
        if not isinstance(changes, dict):
            logger.warning("state_changes 형식 오류 — 객체 아님(%s), 무시", type(changes).__name__)
            return validated

        if "relationship_changes" in changes:
            validated["relationship_changes"] = self._validate_relationship_changes(
                changes["relationship_changes"]
            )

        if "resource_stat_changes" in changes:
            validated["resource_stat_changes"] = []
            for rc in _as_list(changes["resource_stat_changes"], "resource_stat_changes"):
                validated_rc = self._validate_resource_stat_change(rc)
                if validated_rc is not None:
                    validated["resource_stat_changes"].append(validated_rc)

        if "new_memories" in changes:
            validated["new_memories"] = []
            for mem in _as_list(changes["new_memories"], "new_memories"):
                validated_mem = self._validate_memory(mem)
                if validated_mem is not None:
                    validated["new_memories"].append(validated_mem)

        if "npc_memory_updates" in changes:
            validated["npc_memory_updates"] = self._validate_npc_memory_updates(
                changes["npc_memory_updates"]
            )

        if "flag_changes" in changes:
            validated["flag_changes"] = self._validate_flag_changes(changes["flag_changes"])

        return validated

    def _validate_flag_changes(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw[:MAX_FLAG_CHANGES_PER_TURN]:
            if not isinstance(item, dict):
                continue
            key = normalize_flag_key(item.get("key"))
            if not key or key in seen:
                continue
            if "value" not in item:
                continue
            raw_value = item["value"]
            if isinstance(raw_value, bool):
                value: bool | str | int | float = raw_value
            else:
                norm = normalize_flag_value(raw_value)
                if norm is None:
                    continue
                value = norm
            reason = str(item.get("reason", "")).strip()
            if len(reason) < MIN_FLAG_REASON_LEN:
                logger.warning("플래그 변경 거부 — reason 부족: %s", key)
                continue
            seen.add(key)
            out.append({"key": key, "value": value, "reason": reason})
        return out

    def _validate_relationship_changes(self, raw: Any) -> list[dict[str, Any]]:
        """관계 변경 목록 — 건수·합계 캡 적용."""
        raw = _as_list(raw, "relationship_changes")
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

    def _validate_relationship_change(self, change: Any) -> dict[str, Any] | None:
        """관계 변경 검증 — 개연성 ``reason`` 필수."""
        if not isinstance(change, dict):
            logger.warning("관계 변화 형식 오류 — 객체 아님: %r", change)
            return None
        character = _text(change.get("character"))
        stat = _text(change.get("stat"))
        reason = _text(change.get("reason"))

        if not character or (self.valid_characters and character not in self.valid_characters):
            logger.warning(f"존재하지 않는 캐릭터: {character}")
            return None

        if stat not in self.valid_stats:
            logger.warning(f"유효하지 않은 관계 스탯: {stat}")
            return None

        amount = _coerce_int(change.get("change", 0))
        if amount is None:
            logger.warning("관계 변화량 형식 오류: %r", change.get("change"))
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

    def _validate_resource_stat_change(self, change: Any) -> dict[str, Any] | None:
        if not isinstance(change, dict):
            logger.warning("자원 스탯 변화 형식 오류 — 객체 아님: %r", change)
            return None
        key = _text(change.get("key"))
        if not key:
            return None
        if self.valid_resource_stats and key not in self.valid_resource_stats:
            logger.warning("유효하지 않은 자원 스탯 키: %s", key)
            return None
        amount = _coerce_int(change.get("change", 0))
        if amount is None:
            logger.warning("자원 스탯 변화량 형식 오류: %s %r", key, change.get("change"))
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
            "reason": _text(change.get("reason")),
        }
        if "show_card" in change:
            show = change["show_card"]
            if isinstance(show, str):  # "false" 문자열이 True 로 바뀌지 않게
                show = show.strip().lower() in {"true", "1", "yes"}
            out["show_card"] = bool(show)
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
            if emotion not in VALID_EMOTIONS:
                emotion = "neutral"
            out.append({
                "character": character,
                "summary": summary,
                "emotion": emotion,
            })
        return out

    def _validate_memory(self, memory: Any) -> dict[str, Any] | None:
        """기억 검증 — content 는 문자열 필수, importance 는 정수 1~10 으로 정규화."""
        if not isinstance(memory, dict):
            logger.warning("기억 형식 오류 — 객체 아님: %r", memory)
            return None
        content = _text(memory.get("content"))
        if len(content) < 2:
            logger.warning("빈 기억 무시")
            return None

        raw_importance = memory.get("importance", DEFAULT_MEMORY_IMPORTANCE)
        importance = _coerce_int(raw_importance)
        if importance is None:
            logger.warning(
                "기억 중요도 형식 오류(%r) → 기본값 %d", raw_importance, DEFAULT_MEMORY_IMPORTANCE
            )
            importance = DEFAULT_MEMORY_IMPORTANCE
        importance = max(1, min(10, importance))  # 1-10 범위 제한

        emotion = _text(memory.get("emotion")) or "neutral"
        if emotion not in VALID_EMOTIONS:
            emotion = "neutral"

        return {
            "content": content,
            "emotion": emotion,
            "importance": importance,
        }
