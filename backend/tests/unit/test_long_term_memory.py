# backend/tests/unit/test_long_term_memory.py

import pytest
import tempfile
import json
from pathlib import Path
from backend.src.engine.long_term_memory import LongTermMemory


@pytest.fixture
def temp_storage():
    """임시 저장소 fixture"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # 정리
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def memory_system(temp_storage):
    """LongTermMemory 인스턴스 fixture"""
    return LongTermMemory(storage_path=temp_storage)


def test_add_memory(memory_system):
    """기억 추가 테스트"""
    memory_id = memory_system.add_memory(
        content="벨라에게 키스했다",
        emotion="joy",
        importance=10
    )
    
    assert memory_id is not None
    assert len(memory_system.memories) == 1
    
    memory = memory_system.memories[0]
    assert memory["content"] == "벨라에게 키스했다"
    assert memory["emotion"] == "joy"
    assert memory["importance"] == 10
    assert memory["player_id"] == "default"


def test_extract_tags(memory_system):
    """자동 태그 추출 테스트"""
    # NPC 이름 태그
    tags = memory_system._extract_tags("벨라에게 키스했다")
    assert "bella" in tags or "벨라" in [t.lower() for t in tags]
    assert "kiss" in tags
    
    # 행동 키워드
    tags = memory_system._extract_tags("엘레나와 결투했다")
    assert "elena" in tags or "엘레나" in [t.lower() for t in tags]
    assert "duel" in tags
    
    # 장소
    tags = memory_system._extract_tags("도서관에서 공부했다")
    assert any("도서관" in t for t in tags)


def test_search_by_importance(memory_system):
    """중요도 기반 검색 테스트"""
    # 다양한 중요도로 기억 추가
    memory_system.add_memory("일반 대화", importance=3)
    memory_system.add_memory("중요한 약속", importance=7)
    memory_system.add_memory("매우 중요한 사건", importance=10)
    
    # 중요도 7 이상만 검색
    results = memory_system.search(min_importance=7, limit=10)
    
    assert len(results) == 2
    assert all(m["importance"] >= 7 for m in results)
    # 중요도 순으로 정렬되어야 함
    assert results[0]["importance"] >= results[1]["importance"]


def test_search_by_keyword(memory_system):
    """키워드 기반 검색 테스트"""
    memory_system.add_memory("벨라와 식사했다", importance=8)
    memory_system.add_memory("엘레나와 대화했다", importance=6)
    memory_system.add_memory("루아를 만났다", importance=5)
    
    # "벨라" 키워드로 검색
    results = memory_system.search(query="벨라", min_importance=5)
    
    assert len(results) >= 1
    assert any("벨라" in m["content"] for m in results)


def test_search_by_tags(memory_system):
    """태그 기반 검색 테스트"""
    memory_system.add_memory("벨라에게 키스했다", importance=10)
    memory_system.add_memory("벨라와 식사했다", importance=8)
    memory_system.add_memory("엘레나와 싸웠다", importance=7)
    
    # 태그 매칭
    results = memory_system.search(query="벨라", min_importance=5)
    
    assert len(results) >= 2
    # 벨라 관련 기억이 우선
    assert "벨라" in results[0]["content"]


def test_relevance_scoring(memory_system):
    """관련성 점수 계산 테스트"""
    memory1 = {
        "content": "벨라에게 키스했다",
        "tags": ["bella", "kiss"],
        "importance": 10
    }
    memory2 = {
        "content": "엘레나와 대화했다",
        "tags": ["elena", "conversation"],
        "importance": 5
    }
    
    query = "벨라 키스"
    query_tags = memory_system._extract_tags(query)
    
    score1 = memory_system._calculate_relevance(memory1, query, query_tags)
    score2 = memory_system._calculate_relevance(memory2, query, query_tags)
    
    # memory1이 더 관련성 높아야 함
    assert score1 > score2


def test_get_recent(memory_system):
    """최근 기억 반환 테스트"""
    import time
    
    memory_system.add_memory("첫 번째 기억", importance=5)
    time.sleep(0.01)  # 시간 차이
    memory_system.add_memory("두 번째 기억", importance=5)
    time.sleep(0.01)
    memory_system.add_memory("세 번째 기억", importance=5)
    
    recent = memory_system.get_recent(limit=2)
    
    assert len(recent) == 2
    # 최신 순서
    assert recent[0]["content"] == "세 번째 기억"
    assert recent[1]["content"] == "두 번째 기억"


def test_importance_clamping(memory_system):
    """중요도 범위 제한 테스트"""
    # 범위 초과
    memory_system.add_memory("테스트", importance=15)
    assert memory_system.memories[-1]["importance"] == 10
    
    # 범위 미만
    memory_system.add_memory("테스트2", importance=-5)
    assert memory_system.memories[-1]["importance"] == 1


def test_player_id_filtering(memory_system):
    """플레이어별 기억 분리 테스트"""
    memory_system.add_memory("플레이어1 기억", player_id="player1", importance=8)
    memory_system.add_memory("플레이어2 기억", player_id="player2", importance=8)
    memory_system.add_memory("플레이어1 기억2", player_id="player1", importance=7)
    
    # player1 기억만 검색
    results = memory_system.search(player_id="player1", min_importance=5)
    
    assert len(results) == 2
    assert all(m["player_id"] == "player1" for m in results)


def test_persistence(temp_storage):
    """저장/로드 테스트"""
    # 첫 번째 인스턴스
    mem1 = LongTermMemory(storage_path=temp_storage)
    mem1.add_memory("영구 기억", importance=9)
    mem1.add_memory("중요한 사건", importance=10)
    
    assert len(mem1.memories) == 2
    
    # 두 번째 인스턴스 (같은 파일)
    mem2 = LongTermMemory(storage_path=temp_storage)
    
    # 로드되었는지 확인
    assert len(mem2.memories) == 2
    assert mem2.memories[0]["content"] == "영구 기억"


def test_get_stats(memory_system):
    """통계 반환 테스트"""
    memory_system.add_memory("기쁜 일", emotion="joy", importance=8)
    memory_system.add_memory("화난 일", emotion="anger", importance=7)
    memory_system.add_memory("또 기쁜 일", emotion="joy", importance=9)
    
    stats = memory_system.get_stats()
    
    assert stats["total"] == 3
    assert stats["avg_importance"] == pytest.approx(8.0, abs=0.1)
    assert stats["emotions"]["joy"] == 2
    assert stats["emotions"]["anger"] == 1
    assert "top_tags" in stats


def test_empty_search(memory_system):
    """빈 검색 테스트"""
    # 기억이 없을 때
    results = memory_system.search(query="테스트")
    assert results == []
    
    # 매칭되는 것이 없을 때
    memory_system.add_memory("전혀 다른 내용", importance=5)
    results = memory_system.search(query="벨라", min_importance=8)
    assert results == []


def test_multiple_tags_matching(memory_system):
    """여러 태그 매칭 테스트"""
    memory_system.add_memory(
        "벨라에게 결투장에서 키스했다",
        importance=10
    )
    
    # 여러 태그가 추출되어야 함
    memory = memory_system.memories[-1]
    tags = memory["tags"]
    
    # 최소 2개 이상의 태그
    assert len(tags) >= 2
    # 벨라 + 키스 관련 태그 포함
    assert any("bella" in t.lower() or "벨라" in t for t in tags)
    assert "kiss" in tags