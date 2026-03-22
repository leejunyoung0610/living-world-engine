# backend/src/utils/usage_tracker.py

"""
API 사용량 및 비용 추적기

Claude API 호출 시 토큰 사용량을 기록하고
비용을 계산하여 통계를 제공합니다.
"""

from typing import Dict, List


class UsageTracker:
    """API 사용량 및 비용 추적"""

    # Sonnet 4.5 (참고: https://www.anthropic.com/pricing)
    SONNET_INPUT_PRICE = 3.00  # $/1M tokens
    SONNET_OUTPUT_PRICE = 15.00  # $/1M tokens
    SONNET_CACHE_CREATION_PRICE = 3.75  # $/1M tokens
    SONNET_CACHE_READ_PRICE = 0.30  # $/1M tokens

    # Haiku 4.5 (입·출력; 캐시는 Sonnet 대비 입력 단가 비율로 근사)
    HAIKU_INPUT_PRICE = 1.00
    HAIKU_OUTPUT_PRICE = 5.00
    HAIKU_CACHE_CREATION_PRICE = 1.25  # ≈ Sonnet 비율(3.75/3) × 1.0
    HAIKU_CACHE_READ_PRICE = 0.10  # ≈ Sonnet 비율(0.30/3) × 1.0

    def __init__(self, llm_model: str | None = None):
        """llm_model 에 'haiku' 가 포함되면 Haiku 단가, 아니면 Sonnet 단가."""
        lower = (llm_model or "").lower()
        if "haiku" in lower:
            self._input_price = self.HAIKU_INPUT_PRICE
            self._output_price = self.HAIKU_OUTPUT_PRICE
            self._cache_creation_price = self.HAIKU_CACHE_CREATION_PRICE
            self._cache_read_price = self.HAIKU_CACHE_READ_PRICE
        else:
            self._input_price = self.SONNET_INPUT_PRICE
            self._output_price = self.SONNET_OUTPUT_PRICE
            self._cache_creation_price = self.SONNET_CACHE_CREATION_PRICE
            self._cache_read_price = self.SONNET_CACHE_READ_PRICE

        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation = 0
        self.total_cache_read = 0
        self.total_cost = 0.0
        self.turn_costs: List[Dict] = []

    @staticmethod
    def standard_input_billable(
        input_tokens: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
    ) -> int:
        """한 번의 Messages API 응답에 대해 표준 입력 단가가 적용되는 토큰 수 근사.

        Anthropic은 input_tokens / cache_creation / cache_read 를 각각 다른 단가로 청구한다.
        기존 구현은 (특히 2-pass 툴 플로우에서) input_tokens 합에 전부 표준 단가를 곱해
        캐시 히트 토큰을 이중 과금하는 버그가 있었다.

        휴리스틱 (로그·수동 검산과 일치):
        - cache_read > input_tokens: 신규 메시지와 캐시 블록이 비중첩(2차 호출 패턴)
        - 그 외 cache_creation > 0 이고 input_tokens >= cache_creation: 생성분은 쓰기 단가만
        - 그 외: cache_read 만큼은 읽기 단가로 별도 과금 → 표준 입력에서 제외
        """
        if cache_read_tokens > input_tokens:
            return input_tokens
        if cache_creation_tokens > 0 and input_tokens >= cache_creation_tokens:
            return max(0, input_tokens - cache_creation_tokens)
        return max(0, input_tokens - cache_read_tokens)

    def log_call(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        """단일 API 응답 1건 기준 비용 (캐시 필드와 input_tokens 중복 과금 방지)."""
        std_in = self.standard_input_billable(
            input_tokens, cache_creation_tokens, cache_read_tokens
        )
        input_cost = (std_in / 1_000_000) * self._input_price
        output_cost = (output_tokens / 1_000_000) * self._output_price
        cache_create_cost = (cache_creation_tokens / 1_000_000) * self._cache_creation_price
        cache_read_cost = (cache_read_tokens / 1_000_000) * self._cache_read_price
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

    def log_turn_anthropic(
        self,
        segments: List[Dict[str, int]],
    ) -> float:
        """한 게임 턴에 Messages 호출이 1~N번이어도 요청별 과금 후 합산 (턴당 기록 1행).

        툴 2-pass 시 segments 길이 2. 각 세그먼트에 대해 캐시 토큰 이중 과금을 피한다.
        """
        turn_cost = 0.0
        turn_in = turn_out = turn_cc = turn_cr = 0
        for seg in segments:
            inp = int(seg.get("input_tokens", 0))
            out = int(seg.get("output_tokens", 0))
            cc = int(seg.get("cache_creation_tokens", 0))
            cr = int(seg.get("cache_read_tokens", 0))
            std = self.standard_input_billable(inp, cc, cr)
            turn_cost += (std / 1_000_000) * self._input_price
            turn_cost += (out / 1_000_000) * self._output_price
            turn_cost += (cc / 1_000_000) * self._cache_creation_price
            turn_cost += (cr / 1_000_000) * self._cache_read_price
            turn_in += inp
            turn_out += out
            turn_cc += cc
            turn_cr += cr

        self.total_calls += 1
        self.total_input_tokens += turn_in
        self.total_output_tokens += turn_out
        self.total_cache_creation += turn_cc
        self.total_cache_read += turn_cr
        self.total_cost += turn_cost
        self.turn_costs.append({
            "call": self.total_calls,
            "input_tokens": turn_in,
            "output_tokens": turn_out,
            "cache_creation": turn_cc,
            "cache_read": turn_cr,
            "cost": round(turn_cost, 6),
        })
        return turn_cost

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
            with_cache = (stats["total_cache_read"] / 1_000_000) * self.SONNET_CACHE_READ_PRICE
            saved = without_cache - with_cache
            print(f"  Saved:   ${saved:.6f} (90% discount)")
        print("=" * 60 + "\n")