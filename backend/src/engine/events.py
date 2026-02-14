"""
EventManager - 이벤트 시스템

조건 기반으로 이벤트를 트리거하고 관리합니다.
조건 타입: turn_range, variable_threshold, relationship_threshold
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Any

OPERATORS: dict[str, Any] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


class EventManager:
    """조건 기반 이벤트 관리"""

    def __init__(self) -> None:
        self.event_templates: list[dict[str, Any]] = []
        self.triggered_events: list[dict[str, Any]] = []
        self.cooldowns: dict[str, int] = {}  # event_id → 남은 쿨다운 턴

    # ── 로딩 ──

    def load_events(self, events_data: list[dict[str, Any]]) -> None:
        """이벤트 템플릿을 리스트 데이터로 로드"""
        self.event_templates = events_data

    def load_events_from_file(self, filepath: str | Path) -> None:
        """events.json 파일에서 이벤트 로드

        Raises:
            FileNotFoundError: 파일 없음
            json.JSONDecodeError: JSON 파싱 실패
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"이벤트 파일을 찾을 수 없습니다: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.event_templates = data

    # ── 조건 체크 ──

    def check_events(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """현재 상태에서 트리거 가능한 이벤트 목록 반환

        Args:
            state: WorldState.snapshot() 결과
        """
        triggered: list[dict[str, Any]] = []

        for event in self.event_templates:
            event_id = event.get("id", "")

            # 쿨다운 중이면 스킵
            if event_id in self.cooldowns:
                continue

            condition = event.get("condition", {})
            if self._evaluate_condition(condition, state):
                triggered.append(event)

        return triggered

    def _evaluate_condition(self, condition: dict[str, Any], state: dict[str, Any]) -> bool:
        """단일 조건 평가"""
        cond_type = condition.get("type", "")

        if cond_type == "turn_range":
            turn = state.get("turn", 0)
            return condition.get("min_turn", 0) <= turn < condition.get("max_turn", 999)

        elif cond_type == "variable_threshold":
            variable = condition.get("variable", "")
            world_vars = state.get("world", {}).get("world_variables", {})
            actual = world_vars.get(variable, 0)
            return self._compare(actual, condition.get("op", ">="), condition.get("value", 0))

        elif cond_type == "relationship_threshold":
            stat = condition.get("stat", "")
            op_str = condition.get("op", ">=")
            threshold = condition.get("value", 0)
            relationships = state.get("player", {}).get("relationships", {})
            # 어떤 NPC라도 조건 충족하면 True
            for _npc_id, stats in relationships.items():
                if self._compare(stats.get(stat, 0), op_str, threshold):
                    return True
            return False

        return False

    @staticmethod
    def _compare(actual: Any, op_str: str, threshold: Any) -> bool:
        """연산자 문자열로 비교"""
        op_func = OPERATORS.get(op_str)
        if op_func is None:
            return False
        return op_func(actual, threshold)

    # ── 이벤트 발동 ──

    def trigger_event(self, event_id: str) -> dict[str, Any] | None:
        """이벤트 발동: 쿨다운 설정 + 히스토리 기록

        Returns:
            발동된 이벤트 dict, 없으면 None
        """
        event = self._get_event(event_id)
        if event is None:
            return None

        self.cooldowns[event_id] = event.get("cooldown", 10)
        self.triggered_events.append({"id": event_id, "event": event})
        return event

    def _get_event(self, event_id: str) -> dict[str, Any] | None:
        """ID로 이벤트 템플릿 조회"""
        for event in self.event_templates:
            if event.get("id") == event_id:
                return event
        return None

    # ── 쿨다운 ──

    def tick_cooldowns(self) -> None:
        """쿨다운 1턴 감소, 0 이하면 제거"""
        expired = []
        for event_id, remaining in self.cooldowns.items():
            self.cooldowns[event_id] = remaining - 1
            if remaining - 1 <= 0:
                expired.append(event_id)

        for event_id in expired:
            del self.cooldowns[event_id]
