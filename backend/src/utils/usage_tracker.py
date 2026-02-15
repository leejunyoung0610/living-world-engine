# backend/src/utils/usage_tracker.py

"""
API 사용량 및 비용 추적기

Claude API 호출 시 토큰 사용량을 기록하고
비용을 계산하여 통계를 제공합니다.
"""

from typing import Dict, List


class UsageTracker:
    """API 사용량 및 비용 추적"""

    # Claude Sonnet 4.5 가격 (2026년 2월 기준)
    SONNET_INPUT_PRICE = 3.00  # $/1M tokens
    SONNET_OUTPUT_PRICE = 15.00  # $/1M tokens

    def __init__(self):
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.turn_costs: List[Dict] = []

    def log_call(self, input_tokens: int, output_tokens: int) -> float:
        """
        API 호출 기록

        Args:
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수

        Returns:
            이번 호출 비용
        """
        # 비용 계산
        input_cost = (input_tokens / 1_000_000) * self.SONNET_INPUT_PRICE
        output_cost = (output_tokens / 1_000_000) * self.SONNET_OUTPUT_PRICE
        call_cost = input_cost + output_cost

        # 누적
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += call_cost

        # 턴별 기록
        self.turn_costs.append({
            "call": self.total_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(call_cost, 6),
        })

        return call_cost

    def get_stats(self) -> Dict:
        """통계 반환"""
        total_tokens = self.total_input_tokens + self.total_output_tokens
        avg_cost = self.total_cost / len(self.turn_costs) if self.turn_costs else 0

        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": total_tokens,
            "total_cost": round(self.total_cost, 6),
            "avg_cost_per_turn": round(avg_cost, 6),
            "avg_input_tokens": round(self.total_input_tokens / self.total_calls)
            if self.total_calls else 0,
            "avg_output_tokens": round(self.total_output_tokens / self.total_calls)
            if self.total_calls else 0,
        }

    def get_turn_history(self) -> List[Dict]:
        """턴별 비용 기록 반환"""
        return self.turn_costs

    def print_summary(self) -> None:
        """요약 출력"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 API Usage Summary")
        print("="*60)
        print(f"Turns Played: {stats['total_calls']}")
        print(f"Total Cost: ${stats['total_cost']:.6f}")
        print(f"Avg Cost/Turn: ${stats['avg_cost_per_turn']:.6f}")
        print("\nToken Usage:")
        print(f"  Input:  {stats['total_input_tokens']:,} tokens "
              f"(avg {stats['avg_input_tokens']}/turn)")
        print(f"  Output: {stats['total_output_tokens']:,} tokens "
              f"(avg {stats['avg_output_tokens']}/turn)")
        print(f"  Total:  {stats['total_tokens']:,} tokens")
        print("="*60 + "\n")