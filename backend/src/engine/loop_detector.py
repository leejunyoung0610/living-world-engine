"""
LoopDetector - 대화 루프 감지 및 방지

상태 정체와 대사 반복을 감지하고 강제 이벤트를 주입합니다.

TODO: Week 2 Day 11-12에 구현 완성
"""

from __future__ import annotations

from collections import deque
from typing import Any


class LoopDetector:
    """대화 루프 감지 및 방지"""

    STAGNATION_THRESHOLD = 0.05  # 상태 변화 최소값
    SIMILARITY_THRESHOLD = 0.8  # 대사 유사도 임계값
    MIN_STATES_FOR_DETECTION = 5  # 감지 최소 턴 수

    def __init__(self) -> None:
        self.recent_states: deque[dict[str, Any]] = deque(maxlen=10)
        self.recent_responses: deque[str] = deque(maxlen=5)

    def record_state(self, state: dict[str, Any]) -> None:
        """현재 상태 기록"""
        self.recent_states.append(state)

    def record_response(self, response: str) -> None:
        """응답 기록"""
        self.recent_responses.append(response)

    def detect_stagnation(self) -> bool:
        """상태 변화가 없는지 감지"""
        if len(self.recent_states) < self.MIN_STATES_FOR_DETECTION:
            return False

        states = list(self.recent_states)
        changes = []
        for i in range(1, len(states)):
            change = self._calculate_change(states[i - 1], states[i])
            changes.append(change)

        # 최근 변화량이 임계값 미만이면 정체
        recent_changes = changes[-4:] if len(changes) >= 4 else changes
        return sum(recent_changes) < self.STAGNATION_THRESHOLD

    def detect_repetition(self, response: str) -> bool:
        """대사 반복 감지 (현재 응답과 이전 기록된 응답들 비교)"""
        for prev in self.recent_responses:
            if self._similarity(response, prev) > self.SIMILARITY_THRESHOLD:
                return True
        return False

    def is_loop_detected(self, state: dict[str, Any], response: str) -> bool:
        """루프 감지 종합 판정"""
        # 먼저 이전 기록과 비교한 후에 기록 (자기 자신과 비교 방지)
        repetition = self.detect_repetition(response)

        self.record_state(state)
        self.record_response(response)

        stagnation = self.detect_stagnation()

        return stagnation or repetition

    def _calculate_change(self, state1: dict[str, Any], state2: dict[str, Any]) -> float:
        """두 상태 간 변화량 계산"""
        # 간단한 구현: 관계 수치 차이 합산
        diff = 0.0
        rels1 = state1.get("player", {}).get("relationships", {})
        rels2 = state2.get("player", {}).get("relationships", {})

        all_npcs = set(list(rels1.keys()) + list(rels2.keys()))
        for npc in all_npcs:
            r1 = rels1.get(npc, {})
            r2 = rels2.get(npc, {})
            all_stats = set(list(r1.keys()) + list(r2.keys()))
            for stat in all_stats:
                diff += abs(r1.get(stat, 50) - r2.get(stat, 50))

        # 정규화 (0-1 범위)
        if all_npcs:
            return diff / (len(all_npcs) * 100)
        return 0.0

    def _similarity(self, text1: str, text2: str) -> float:
        """두 텍스트의 유사도 (키워드 기반)"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0
