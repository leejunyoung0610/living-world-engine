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