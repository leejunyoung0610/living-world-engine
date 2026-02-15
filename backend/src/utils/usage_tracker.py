# backend/src/utils/usage_tracker.py

"""
API 사용량 및 비용 추적기

Claude API 호출 시 토큰 사용량을 기록하고
비용을 계산하여 통계를 제공합니다.
"""

from typing import Dict, List


class UsageTracker:
    """API 사용량 및 비용 추적"""

    SONNET_INPUT_PRICE = 3.00  # $/1M tokens
    SONNET_OUTPUT_PRICE = 15.00  # $/1M tokens
    CACHE_CREATION_PRICE = 3.75  # $/1M tokens
    CACHE_READ_PRICE = 0.30  # $/1M tokens

    def __init__(self):
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation = 0
        self.total_cache_read = 0
        self.total_cost = 0.0
        self.turn_costs: List[Dict] = []

    def log_call(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        input_cost = (input_tokens / 1_000_000) * self.SONNET_INPUT_PRICE
        output_cost = (output_tokens / 1_000_000) * self.SONNET_OUTPUT_PRICE
        cache_create_cost = (cache_creation_tokens / 1_000_000) * self.CACHE_CREATION_PRICE
        cache_read_cost = (cache_read_tokens / 1_000_000) * self.CACHE_READ_PRICE
        call_cost = input_cost + output_cost + cache_create_cost + cache_read_cost

        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cache_creation += cache_creation_tokens
        self.total_cache_read += cache_read_tokens
        self.total_cost += call_cost

        self.turn_costs.append({
            "call": self.total_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation": cache_creation_tokens,
            "cache_read": cache_read_tokens,
            "cost": round(call_cost, 6),
        })

        return call_cost

    def get_stats(self) -> Dict:
        total_tokens = self.total_input_tokens + self.total_output_tokens
        avg_cost = self.total_cost / len(self.turn_costs) if self.turn_costs else 0
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_creation": self.total_cache_creation,
            "total_cache_read": self.total_cache_read,
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
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 API Usage Summary (with Caching)")
        print("="*60)
        print(f"Turns Played: {stats['total_calls']}")
        print(f"Total Cost: ${stats['total_cost']:.6f}")
        print(f"Avg Cost/Turn: ${stats['avg_cost_per_turn']:.6f}")
        print("\nToken Usage:")
        print(f"  Input:  {stats['total_input_tokens']:,} tokens")
        print(f"  Output: {stats['total_output_tokens']:,} tokens")
        print(f"  Total:  {stats['total_tokens']:,} tokens")
        print("\nCache:")
        print(f"  Created: {stats['total_cache_creation']:,} tokens")
        print(f"  Read:    {stats['total_cache_read']:,} tokens")
        if stats["total_cache_read"] > 0:
            without_cache = (stats["total_cache_read"] / 1_000_000) * self.SONNET_INPUT_PRICE
            with_cache = (stats["total_cache_read"] / 1_000_000) * self.CACHE_READ_PRICE
            saved = without_cache - with_cache
            print(f"  Saved:   ${saved:.6f} (90% discount)")
        print("=" * 60 + "\n")