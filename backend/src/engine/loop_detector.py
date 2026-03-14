"""
LoopDetector - 대화 루프 감지 및 방지

상태 정체와 대사 반복을 감지하고, 심각도를 계산하며,
GameEngine에서 강제 이벤트를 주입할 수 있도록 해결책을 제안합니다.
"""

from __future__ import annotations

import time
import logging
from collections import deque
from typing import Any

logger = logging.getLogger("living_world")


class LoopDetector:
    """대화 루프 감지 및 방지"""

    STAGNATION_THRESHOLD = 0.05  # 상태 변화 최소값
    SIMILARITY_THRESHOLD = 0.8  # 대사 유사도 임계값
    MIN_STATES_FOR_DETECTION = 5  # 감지 최소 턴 수

    def __init__(self) -> None:
        self.recent_states: deque[dict[str, Any]] = deque(maxlen=10)
        self.recent_responses: deque[str] = deque(maxlen=5)

    # ── 기록 ──

    def record_state(self, state: dict[str, Any]) -> None:
        """현재 상태 기록"""
        self.recent_states.append(state)

    def record_response(self, response: str) -> None:
        """응답 기록"""
        self.recent_responses.append(response)

    # ── 통합 감지 (v2) ──

    def detect_loop(
        self, state: dict[str, Any], response: str
    ) -> dict[str, Any]:
        """
        루프 감지 + 심각도 + 해결책 제안

        Returns:
            {
                "detected": bool,
                "type": "stagnation" | "repetition" | None,
                "severity": 0-10,
                "suggested_action": "inject_event" | None,
            }
        """
        start_time = time.time()

        try:
            # 이전 기록과 비교 (자기 자신 비교 방지)
            repetition = self.detect_repetition(response)

            self.record_state(state)
            self.record_response(response)

            stagnation = self.detect_stagnation()

            elapsed = time.time() - start_time

            # ── 정체 우선 (더 심각) ──
            if stagnation:
                severity = self._calculate_stagnation_severity()
                logger.debug(f"Loop detection: {elapsed:.3f}s")
                logger.warning(
                    f"Loop detected: stagnation (severity {severity})"
                )
                return {
                    "detected": True,
                    "type": "stagnation",
                    "severity": severity,
                    "suggested_action": "inject_event",
                }

            # ── 대사 반복 ──
            if repetition:
                severity = self._calculate_repetition_severity(response)
                logger.debug(f"Loop detection: {elapsed:.3f}s")
                logger.warning(
                    f"Loop detected: repetition (severity {severity})"
                )
                return {
                    "detected": True,
                    "type": "repetition",
                    "severity": severity,
                    "suggested_action": "inject_event",
                }

            # ── 정상 ──
            logger.debug(f"Loop detection: {elapsed:.3f}s — no loop")
            return {
                "detected": False,
                "type": None,
                "severity": 0,
                "suggested_action": None,
            }

        except Exception as e:
            logger.error(f"Loop detection failed: {e}", exc_info=True)
            return {
                "detected": False,
                "type": None,
                "severity": 0,
                "suggested_action": None,
            }

    # ── 기본 감지 ──

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
        """루프 감지 종합 판정 (레거시 — detect_loop()을 내부 호출)"""
        result = self.detect_loop(state, response)
        return result["detected"]

    # ── 심각도 계산 ──

    def _calculate_stagnation_severity(self) -> int:
        """
        최근 턴 변화량 기반 심각도 (1-10)

        변화량이 작을수록 심각:
          avg_change < 0.01  →  10
          avg_change < 0.03  →  8
          avg_change < 0.05  →  7
          avg_change < 0.1   →  5
          else               →  3
        """
        states = list(self.recent_states)
        if len(states) < 2:
            return 1

        changes = [
            self._calculate_change(states[i - 1], states[i])
            for i in range(1, len(states))
        ]
        avg_change = sum(changes) / len(changes) if changes else 0

        # 임계값 완화 (기존 0.01 → 0.001)
        if avg_change < 0.001:
            return 10
        if avg_change < 0.01:
            return 8
        if avg_change < 0.05:
            return 6
        if avg_change < 0.1:
            return 4
        return 1

    def _calculate_repetition_severity(self, response: str) -> int:
        """
        반복 횟수 기반 심각도 (1-10)

        유사 응답 수가 많을수록 심각:
          4+ matches  →  10
          3  matches  →  8
          2  matches  →  6
          1  match    →  3
          0  matches  →  1
        """
        match_count = sum(
            1
            for prev in self.recent_responses
            if self._similarity(response, prev) > self.SIMILARITY_THRESHOLD
        )
        # record_response는 이미 detect_loop에서 호출되므로
        # 자기 자신이 포함될 수 있음 → -1 보정
        match_count = max(0, match_count - 1)
        
        if match_count >= 4:
            return 10
        if match_count >= 3:
            return 8
        if match_count >= 2:
            return 6
        if match_count >= 1:
            return 3
        return 1

    # ── 유틸리티 ──

    def _calculate_change(self, state1: dict[str, Any], state2: dict[str, Any]) -> float:
        """두 상태 간 변화량 계산"""
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
        """두 텍스트의 유사도 (키워드 기반 Jaccard)"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0
