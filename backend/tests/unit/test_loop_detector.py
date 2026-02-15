"""
LoopDetector 유닛 테스트
"""

import logging

import pytest

from backend.src.engine.loop_detector import LoopDetector


class TestLoopDetector:
    """LoopDetector 클래스 테스트"""

    def test_no_loop_initially(self) -> None:
        """초기 상태에서는 루프 없음"""
        detector = LoopDetector()
        state = {"player": {"relationships": {"elena": {"affection": 50}}}}
        assert not detector.is_loop_detected(state, "안녕하세요!")

    def test_stagnation_detection(self) -> None:
        """상태 정체 감지"""
        detector = LoopDetector()
        # 동일한 상태를 여러 번 기록
        same_state = {"player": {"relationships": {"elena": {"affection": 50}}}}
        for i in range(10):
            detector.record_state(same_state)

        assert detector.detect_stagnation()

    def test_no_stagnation_with_changes(self) -> None:
        """상태 변화가 있으면 정체 아님"""
        detector = LoopDetector()
        for i in range(10):
            state = {"player": {"relationships": {"elena": {"affection": 50 + i * 5}}}}
            detector.record_state(state)

        assert not detector.detect_stagnation()

    def test_repetition_detection(self) -> None:
        """대사 반복 감지"""
        detector = LoopDetector()
        detector.record_response("안녕하세요 반가워요 오늘 좋은 하루예요")
        detector.record_response("날씨가 좋네요 산책하러 갈까요")

        # 매우 유사한 응답
        assert detector.detect_repetition("안녕하세요 반가워요 오늘 좋은 하루예요")

    def test_no_repetition_with_different_responses(self) -> None:
        """다른 응답은 반복이 아님"""
        detector = LoopDetector()
        detector.record_response("안녕하세요 반가워요")
        detector.record_response("날씨가 좋네요")

        assert not detector.detect_repetition("완전히 다른 내용의 대화입니다 마법을 배우자")

    def test_similarity_calculation(self) -> None:
        """유사도 계산"""
        detector = LoopDetector()

        # 동일 텍스트 = 1.0
        assert detector._similarity("안녕 하세요", "안녕 하세요") == 1.0

        # 빈 텍스트 = 0.0
        assert detector._similarity("", "") == 0.0


class TestDetectLoop:
    """detect_loop() 통합 감지 메서드 테스트"""

    def test_detect_loop_no_loop(self) -> None:
        """정상 대화 — 루프 미감지"""
        detector = LoopDetector()
        state = {"player": {"relationships": {"elena": {"affection": 50}}}}

        result = detector.detect_loop(state, "안녕하세요 반가워요!")
        assert result["detected"] is False
        assert result["type"] is None
        assert result["severity"] == 0
        assert result["suggested_action"] is None

    def test_detect_loop_stagnation_severe(self) -> None:
        """심각한 상태 정체 — severity 7 이상"""
        detector = LoopDetector()
        same_state = {"player": {"relationships": {"elena": {"affection": 50}}}}
        # MIN_STATES_FOR_DETECTION(5) 이상 동일 상태 쌓기
        for _ in range(10):
            detector.record_state(same_state)

        result = detector.detect_loop(same_state, "완전히 새로운 대사입니다 마법을 배우자")
        assert result["detected"] is True
        assert result["type"] == "stagnation"
        assert result["severity"] >= 7
        assert result["suggested_action"] == "inject_event"

    def test_detect_loop_repetition_moderate(self) -> None:
        """대사 반복 감지 — severity 5 이상"""
        detector = LoopDetector()
        repeated = "안녕하세요 반가워요 오늘 좋은 하루예요"
        detector.record_response(repeated)

        state = {"player": {"relationships": {"elena": {"affection": 55}}}}
        result = detector.detect_loop(state, repeated)
        assert result["detected"] is True
        assert result["type"] == "repetition"
        assert result["severity"] >= 5
        assert result["suggested_action"] == "inject_event"

    def test_detect_loop_error_handling(self) -> None:
        """내부 에러 발생 시 Fallback — detected: False 반환"""
        detector = LoopDetector()
        # recent_states에 비정상 데이터 주입
        for _ in range(6):
            detector.recent_states.append("invalid_not_a_dict")

        # 에러가 나도 안전하게 False 반환
        result = detector.detect_loop({}, "테스트")
        assert result["detected"] is False

    def test_performance_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """로깅 정상 동작 확인"""
        detector = LoopDetector()
        same_state = {"player": {"relationships": {"elena": {"affection": 50}}}}
        for _ in range(10):
            detector.record_state(same_state)

        with caplog.at_level(logging.DEBUG, logger="living_world"):
            detector.detect_loop(same_state, "새로운 대사입니다")

        log_text = caplog.text
        assert "Loop detection" in log_text
        assert "Loop detected" in log_text or "detection" in log_text
