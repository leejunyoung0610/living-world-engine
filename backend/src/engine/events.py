"""
EventManager - 이벤트 시스템

조건 기반으로 이벤트를 트리거하고 관리합니다.

TODO: Week 2 Day 8-10에 구현 완성
"""

from __future__ import annotations

from typing import Any


class EventManager:
    """조건 기반 이벤트 관리"""

    def __init__(self) -> None:
        self.event_templates: list[dict[str, Any]] = []
        self.triggered_events: list[dict[str, Any]] = []
        self.cooldowns: dict[str, int] = {}  # event_id → 남은 쿨다운 턴

    def load_events(self, events_data: list[dict[str, Any]]) -> None:
        """이벤트 템플릿 로드"""
        self.event_templates = events_data

    def check_events(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """현재 상태에서 트리거 가능한 이벤트 확인"""
        # TODO: 구현
        triggered = []
        return triggered

    def tick_cooldowns(self) -> None:
        """쿨다운 1턴 감소"""
        expired = []
        for event_id, remaining in self.cooldowns.items():
            self.cooldowns[event_id] = remaining - 1
            if remaining - 1 <= 0:
                expired.append(event_id)

        for event_id in expired:
            del self.cooldowns[event_id]
