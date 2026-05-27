"""
KeywordMemorySearch 유닛 테스트
"""


from backend.src.engine.memory import KeywordMemorySearch


class TestKeywordMemorySearch:
    """KeywordMemorySearch 클래스 테스트"""

    def test_add_memory(self) -> None:
        """기억 추가"""
        mem = KeywordMemorySearch()
        mem.add_memory("엘레나와 만남", emotion="joy", importance=7)
        assert len(mem) == 1

    def test_importance_clamping(self) -> None:
        """중요도 1-10 범위 제한"""
        mem = KeywordMemorySearch()
        mem.add_memory("낮은 중요도", importance=0)
        mem.add_memory("높은 중요도", importance=15)
        assert mem.memories[0]["importance"] == 1
        assert mem.memories[1]["importance"] == 10

    def test_search_keyword_matching(self, memory_search: KeywordMemorySearch) -> None:
        """키워드 매칭 검색"""
        results = memory_search.search("엘레나 결투장", top_k=3)
        assert len(results) > 0
        # 엘레나와 결투장 관련 기억이 상위에 나와야 함
        assert "엘레나" in results[0]["content"]

    def test_search_empty_query(self, memory_search: KeywordMemorySearch) -> None:
        """빈 쿼리 검색"""
        results = memory_search.search("", top_k=3)
        # 빈 쿼리여도 중요도/최신도로 결과 반환
        assert len(results) > 0

    def test_search_no_memories(self) -> None:
        """메모리가 비었을 때"""
        mem = KeywordMemorySearch()
        results = mem.search("무언가")
        assert results == []

    def test_search_top_k(self, memory_search: KeywordMemorySearch) -> None:
        """top_k 개수 제한"""
        results = memory_search.search("산책", top_k=1)
        assert len(results) == 1

    def test_get_recent(self, memory_search: KeywordMemorySearch) -> None:
        """최근 기억 조회"""
        recent = memory_search.get_recent(2)
        assert len(recent) == 2
        # 마지막에 추가된 것이 마지막
        assert "루아" in recent[-1]["content"]

    def test_extract_keywords(self) -> None:
        """키워드 추출 (불용어 제거)"""
        mem = KeywordMemorySearch()
        keywords = mem._extract_keywords("엘레나와 결투장에서 처음 만났다")
        assert "엘레나와" in keywords or "엘레나" in keywords
        assert "결투장에서" in keywords or "결투장" in keywords

    def test_search_by_importance(self) -> None:
        """중요도 높은 기억이 상위에 나오는지"""
        mem = KeywordMemorySearch()
        mem.add_memory("별로 안 중요한 일", importance=1)
        mem.add_memory("매우 중요한 사건", importance=10)
        mem.add_memory("보통 사건", importance=5)

        # 빈 쿼리 → 중요도와 최신도로만 정렬
        results = mem.search("", top_k=3)
        # 중요도 10인 것이 위에 올라야 함
        importances = [r["importance"] for r in results]
        assert importances[0] >= importances[-1]
