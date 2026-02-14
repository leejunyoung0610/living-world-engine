"""
LoopDetector 유닛 테스트
"""

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
