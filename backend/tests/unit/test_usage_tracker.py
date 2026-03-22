# backend/tests/unit/test_usage_tracker.py

"""UsageTracker 유닛 테스트"""

import pytest
from backend.src.utils.usage_tracker import UsageTracker


def test_initial_state():
    """초기 상태 확인"""
    tracker = UsageTracker()
    
    assert tracker.total_calls == 0
    assert tracker.total_input_tokens == 0
    assert tracker.total_output_tokens == 0
    assert tracker.total_cost == 0.0
    assert tracker.turn_costs == []


def test_log_single_call():
    """단일 호출 기록"""
    tracker = UsageTracker()
    
    cost = tracker.log_call(input_tokens=1000, output_tokens=200)
    
    # 비용 계산 확인
    # 1000 * 3/1M = 0.003
    # 200 * 15/1M = 0.003
    # Total = 0.006
    assert cost == pytest.approx(0.006, abs=0.0001)
    
    assert tracker.total_calls == 1
    assert tracker.total_input_tokens == 1000
    assert tracker.total_output_tokens == 200
    assert tracker.total_cost == pytest.approx(0.006, abs=0.0001)


def test_log_multiple_calls():
    """복수 호출 기록"""
    tracker = UsageTracker()
    
    tracker.log_call(1000, 200)  # $0.006
    tracker.log_call(1500, 300)  # $0.009
    tracker.log_call(1200, 250)  # $0.0075
    
    assert tracker.total_calls == 3
    assert tracker.total_input_tokens == 3700
    assert tracker.total_output_tokens == 750
    assert tracker.total_cost == pytest.approx(0.0225, abs=0.001)


def test_get_stats():
    """통계 확인"""
    tracker = UsageTracker()
    
    tracker.log_call(1000, 200)
    tracker.log_call(1500, 300)
    
    stats = tracker.get_stats()
    
    assert stats["total_calls"] == 2
    assert stats["total_input_tokens"] == 2500
    assert stats["total_output_tokens"] == 500
    assert stats["total_tokens"] == 3000
    assert stats["avg_input_tokens"] == 1250
    assert stats["avg_output_tokens"] == 250
    assert stats["avg_cost_per_turn"] == pytest.approx(0.0075, abs=0.0001)


def test_get_turn_history():
    """턴별 기록 확인"""
    tracker = UsageTracker()
    
    tracker.log_call(1000, 200)
    tracker.log_call(1500, 300)
    
    history = tracker.get_turn_history()
    
    assert len(history) == 2
    assert history[0]["call"] == 1
    assert history[0]["input_tokens"] == 1000
    assert history[0]["output_tokens"] == 200
    assert history[1]["call"] == 2
    assert history[1]["input_tokens"] == 1500
    assert history[1]["output_tokens"] == 300


def test_empty_stats():
    """호출 없을 때 통계"""
    tracker = UsageTracker()
    
    stats = tracker.get_stats()
    
    assert stats["total_calls"] == 0
    assert stats["avg_cost_per_turn"] == 0
    assert stats["avg_input_tokens"] == 0


def test_haiku_pricing_when_model_contains_haiku():
    """Haiku 모델 ID면 Haiku 단가 적용"""
    tracker = UsageTracker(llm_model="claude-haiku-4-5-20251001")
    cost = tracker.log_call(input_tokens=1_000_000, output_tokens=1_000_000)
    # 1M * $1 + 1M * $5 = $6
    assert cost == pytest.approx(6.0, abs=0.001)


def test_standard_input_billable_cache_read_subset():
    """2차 호출: cache_read 가 input_tokens 안에 포함된 경우 표준 입력만 분리."""
    assert UsageTracker.standard_input_billable(2016, 0, 1979) == 37


def test_standard_input_billable_cache_read_disjoint():
    """2차 호출: cache_read > input_tokens 이면 전부 표준 입력 (비중첩)."""
    assert UsageTracker.standard_input_billable(1783, 0, 2022) == 1783


def test_standard_input_billable_cache_creation_subset():
    """1차 호출: cache_creation 이 input_tokens 에 포함."""
    assert UsageTracker.standard_input_billable(2562, 2022, 0) == 540


def test_standard_input_billable_creation_disjoint_small_input():
    """캐시 생성 토큰이 input_tokens 보다 크면(비중첩) 표준 입력은 input 전체."""
    assert UsageTracker.standard_input_billable(1784, 1979, 0) == 1784


def test_log_turn_anthropic_no_double_charge_turn8_pattern():
    """툴 2-pass + 프롬프트 캐시 패턴에서 수동 검산과 일치 (Turn 8 로그)."""
    tracker = UsageTracker()
    cost = tracker.log_turn_anthropic(
        [
            {
                "input_tokens": 1784,
                "output_tokens": 0,
                "cache_creation_tokens": 1979,
                "cache_read_tokens": 0,
            },
            {
                "input_tokens": 2016,
                "output_tokens": 747,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 1979,
            },
        ]
    )
    # 입력측: 1784*3 + 1979*3.75 + 37*3 + 1979*0.3 (per M) + 출력 747*15/M
    expected_in = (
        1784 * 3.0 + 1979 * 3.75 + 37 * 3.0 + 1979 * 0.30
    ) / 1_000_000
    expected_out = 747 * 15.0 / 1_000_000
    assert cost == pytest.approx(expected_in + expected_out, abs=1e-5)
    # 구버그(합산 input 전부 표준 단가)였다면 약 0.03062
    assert cost < 0.027