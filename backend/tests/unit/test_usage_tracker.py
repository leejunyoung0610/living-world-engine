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


# Anthropic usage: input_tokens / cache_creation_input_tokens / cache_read_input_tokens 는
# 서로 겹치지 않는다 (총 입력 = 세 값의 합). input_tokens 는 이미 캐시 토큰을 제외한 값.


def test_cache_read_tokens_billed_separately_from_input():
    """캐시 히트: input_tokens 전부 표준 단가 + cache_read 는 읽기 단가 (차감 없음)."""
    tracker = UsageTracker()
    cost = tracker.log_call(
        input_tokens=50,
        output_tokens=0,
        cache_read_tokens=100_000,
    )
    expected = (50 * 3.00 + 100_000 * 0.30) / 1_000_000
    assert cost == pytest.approx(expected, rel=1e-9)


def test_input_smaller_than_cache_read_is_not_zeroed():
    """구 휴리스틱은 input 에서 cache_read 를 빼 표준 입력을 0/과소로 만들 수 있었다."""
    tracker = UsageTracker()
    cost = tracker.log_call(input_tokens=2016, output_tokens=0, cache_read_tokens=1979)
    # 2016 토큰 모두 표준 단가 — (2016 - 1979) = 37 토큰만 과금하던 버그 회귀 방지
    assert cost == pytest.approx((2016 * 3.00 + 1979 * 0.30) / 1_000_000, rel=1e-9)


def test_cache_creation_tokens_billed_at_write_price_only_once():
    """캐시 생성: cache_creation 은 쓰기 단가, input_tokens 는 표준 단가로 각각 1회."""
    tracker = UsageTracker()
    cost = tracker.log_call(
        input_tokens=2562,
        output_tokens=100,
        cache_creation_tokens=2022,
    )
    expected = (2562 * 3.00 + 100 * 15.00 + 2022 * 3.75) / 1_000_000
    assert cost == pytest.approx(expected, rel=1e-9)


def test_haiku_cache_prices():
    tracker = UsageTracker(llm_model="claude-haiku-4-5-20251001")
    cost = tracker.log_call(
        input_tokens=1_000_000,
        output_tokens=0,
        cache_creation_tokens=1_000_000,
        cache_read_tokens=1_000_000,
    )
    # $1 + $1.25 + $0.10
    assert cost == pytest.approx(2.35, rel=1e-9)


def test_log_turn_anthropic_two_pass_sums_each_segment():
    """툴 2-pass + 프롬프트 캐시: 세그먼트마다 네 필드를 각 단가로 합산."""
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
    expected = (
        1784 * 3.00 + 1979 * 3.75  # 1차: 표준 입력 + 캐시 쓰기
        + 2016 * 3.00 + 1979 * 0.30  # 2차: 표준 입력 + 캐시 읽기
        + 747 * 15.00  # 출력
    ) / 1_000_000
    assert cost == pytest.approx(expected, rel=1e-9)
    assert tracker.total_calls == 1  # 턴당 1행
    assert tracker.total_input_tokens == 1784 + 2016
    assert tracker.total_cache_creation == 1979
    assert tracker.total_cache_read == 1979
    assert tracker.get_turn_history()[0]["cost"] == pytest.approx(round(expected, 6))


def test_log_turn_matches_sum_of_log_calls():
    segments = [
        {"input_tokens": 300, "output_tokens": 20, "cache_creation_tokens": 0, "cache_read_tokens": 4000},
        {"input_tokens": 120, "output_tokens": 400, "cache_creation_tokens": 500, "cache_read_tokens": 4000},
    ]
    per_call = UsageTracker()
    for seg in segments:
        per_call.log_call(
            seg["input_tokens"],
            seg["output_tokens"],
            seg["cache_creation_tokens"],
            seg["cache_read_tokens"],
        )
    per_turn = UsageTracker()
    per_turn.log_turn_anthropic(segments)
    assert per_turn.total_cost == pytest.approx(per_call.total_cost, rel=1e-12)
