"""
KeywordMemorySearch - 키워드 기반 메모리 검색 시스템

벡터 DB 없이 키워드 매칭 + 중요도 + 최신도로 관련 기억을 검색합니다.

TODO: Week 1 Day 3-4에 구현 완성
"""

from __future__ import annotations

import time
from typing import Any


# 한국어 불용어
STOPWORDS = {"은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "로", "에서", "으로"}


class KeywordMemorySearch:
    """간단하지만 효과적인 키워드 기반 메모리 검색"""

    def __init__(self) -> None:
        self.memories: list[dict[str, Any]] = []

    def add_memory(self, content: str, emotion: str = "neutral", importance: int = 5, **kwargs: Any) -> None:
        """새 기억 추가"""
        memory = {
            "content": content,
            "emotion": emotion,
            "importance": max(1, min(10, importance)),  # 1-10 범위
            "timestamp": time.time(),
            "keywords": self._extract_keywords(content),
            **kwargs,
        }
        self.memories.append(memory)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """쿼리와 가장 관련 높은 기억 top_k개 반환"""
        if not self.memories:
            return []

        query_keywords = set(self._extract_keywords(query))

        scored_memories: list[tuple[float, dict[str, Any]]] = []

        for memory in self.memories:
            content_keywords = set(memory.get("keywords", []))

            # 1. 키워드 매칭 점수
            if not query_keywords:
                keyword_score = 0.0
            else:
                keyword_score = len(query_keywords & content_keywords) / len(query_keywords)

            # 2. 중요도 가중치 (1-10 → 0.1-1.0)
            importance_score = memory.get("importance", 5) / 10.0

            # 3. 최신도 가중치 (최근일수록 높음)
            recency_score = self._calculate_recency(memory.get("timestamp", 0))

            # 종합 점수
            total_score = keyword_score * 0.5 + importance_score * 0.3 + recency_score * 0.2

            scored_memories.append((total_score, memory))

        # 점수순 정렬
        scored_memories.sort(reverse=True, key=lambda x: x[0])

        return [m for _, m in scored_memories[:top_k]]

    def get_recent(self, count: int = 5) -> list[dict[str, Any]]:
        """가장 최근 기억 count개 반환"""
        return self.memories[-count:]

    def _extract_keywords(self, text: str) -> list[str]:
        """간단한 키워드 추출 (불용어 제거)"""
        words = text.split()
        return [w for w in words if w not in STOPWORDS and len(w) > 1]

    def _calculate_recency(self, timestamp: float) -> float:
        """최신도 점수 계산 (0.0 ~ 1.0)"""
        if timestamp == 0:
            return 0.0

        age_seconds = time.time() - timestamp
        age_hours = age_seconds / 3600

        # 1시간 이내 = 1.0, 24시간 이후 = 0.1
        if age_hours <= 1:
            return 1.0
        elif age_hours <= 24:
            return max(0.1, 1.0 - (age_hours / 24) * 0.9)
        else:
            return 0.1

    def __len__(self) -> int:
        return len(self.memories)
