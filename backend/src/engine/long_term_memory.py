# backend/src/engine/long_term_memory.py

import json
import uuid
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def normalize_query(query: str) -> List[str]:
    """쿼리를 확장하여 동의어/영어/태그를 포함하게 함"""
    keywords: List[str] = []
    q_lower = query.lower()

    name_map = {
        "루아": ["루아", "lua"],
        "벨라": ["벨라", "bella"],
        "엘레나": ["엘레나", "elena"],
        "세인": ["세인", "sein"],
        "록산느": ["록산느", "roxanne"],
        "레오": ["레오", "leo"],
    }
    for kr, synonyms in name_map.items():
        if kr in query or any(en in query.lower() for en in synonyms):
            keywords.extend(synonyms)

    action_map = {
        "키스": ["키스", "kiss", "romance"],
        "결투": ["결투", "duel", "fight"],
        "공격": ["공격", "attack"],
        "대화": ["대화", "conversation"],
        "식사": ["식사", "meal"],
    }
    for kr, synonyms in action_map.items():
        if kr in query:
            keywords.extend(synonyms)

    keywords.append(q_lower)
    return list(dict.fromkeys(keywords))


class LongTermMemory:
    """장기 기억 시스템 - JSON 기반 (Week 3에 PostgreSQL 전환)"""
    
    def __init__(self, storage_path: str = "data/memories.json"):
        self.storage_path = Path(storage_path)
        self.memories: List[Dict] = []
        self._load()
    
    def _load(self):
        """저장된 기억 로드"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = data.get('memories', [])
                logger.info(f"Loaded {len(self.memories)} memories")
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")
                self.memories = []
        else:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.memories = []
    
    def _save(self):
        """기억 저장"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({'memories': self.memories}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")
    
    def add_memory(
        self,
        content: str,
        emotion: str = "neutral",
        importance: int = 5,
        player_id: str = "default",
    ) -> str:
        """기억 추가 - 자동 태깅
        
        Args:
            content: 기억 내용
            emotion: 감정 (joy, anger, fear, sadness, neutral)
            importance: 중요도 (1-10)
            player_id: 플레이어 ID
        
        Returns:
            memory_id: 생성된 기억 ID
        """
        # 자동 태그 추출
        tags = self._extract_tags(content)
        
        if self._is_duplicate(content):
            logger.info(f"Duplicate memory skipped: {content[:50]}...")
            return ""

        memory = {
            "id": uuid.uuid4().hex,
            "player_id": player_id,
            "content": content,
            "emotion": emotion,
            "importance": max(1, min(100, importance)),
            "tags": tags,
            "created_at": datetime.now().isoformat(),
        }
        
        self.memories.append(memory)
        self._save()
        
        logger.debug(f"Added memory: {content[:50]}... (importance: {importance}, tags: {tags[:3]})")
        
        return memory["id"]
    
    def _extract_tags(self, content: str) -> List[str]:
        """자동 태그 추출
        
        규칙:
        1. 고유명사 (NPC 이름)
        2. 행동 키워드 (키스, 공격, 대화 등)
        3. 장소
        4. 감정 키워드
        """
        tags = []
        content_lower = content.lower()
        
        # 1. NPC 이름 (하드코딩, 나중에 동적으로)
        npc_names = ["엘레나", "벨라", "루아", "세인", "록산느", "레오",
                     "elena", "bella", "lua", "sein", "roxanne", "leo"]
        for name in npc_names:
            if name in content_lower:
                tags.append(name.lower())
        
        # 2. 행동 키워드
        action_keywords = {
            "키스": "kiss",
            "공격": "attack",
            "대화": "conversation",
            "흑마법": "dark_magic",
            "결투": "duel",
            "식사": "meal",
            "선물": "gift",
            "도움": "help",
            "싸움": "fight",
            "칭찬": "compliment",
            "모욕": "insult",
        }
        for kr, en in action_keywords.items():
            if kr in content:
                tags.append(en)
        
        # 3. 장소
        location_keywords = ["복도", "결투장", "도서관", "식당", "교실", "기숙사"]
        for loc in location_keywords:
            if loc in content:
                tags.append(f"location_{loc}")
        
        # 4. 감정 키워드
        emotion_keywords = {
            "화": "angry",
            "기쁨": "happy",
            "슬픔": "sad",
            "두려움": "fear",
            "설레": "excited",
            "당황": "embarrassed",
        }
        for kr, en in emotion_keywords.items():
            if kr in content:
                tags.append(f"emotion_{en}")
        
        return list(set(tags))  # 중복 제거
    
    def search(
        self,
        query: str = "",
        player_id: str = "default",
        min_importance: int = 5,
        limit: int = 5,
    ) -> List[Dict]:
        """기억 검색 - 중요도 + 관련성 기반
        
        Args:
            query: 검색 쿼리 (키워드)
            player_id: 플레이어 ID
            min_importance: 최소 중요도
            limit: 최대 결과 수
        
        Returns:
            관련 기억 리스트 (중요도 순)
        """
        # 1. 플레이어 필터링
        player_memories = [
            m for m in self.memories 
            if m.get("player_id") == player_id
        ]
        
        if not player_memories:
            return []
        
        # 2. 쿼리가 없으면 중요도만으로 정렬
        if not query:
            filtered = [
                m for m in player_memories
                if m.get("importance", 0) >= min_importance
            ]
            # 중요도 순 정렬
            filtered.sort(
                key=lambda m: (m.get("importance", 0), m.get("created_at", "")),
                reverse=True
            )
            return filtered[:limit]
        
        # 3. 쿼리 관련성 점수 계산
        scored_memories = []
        keywords = normalize_query(query)
        query_tags = list(set(self._extract_tags(query) + keywords))
        
        for memory in player_memories:
            # 중요도 필터
            if memory.get("importance", 0) < min_importance:
                continue
            
            # 관련성 점수 계산
            score = self._calculate_relevance(
                memory=memory,
                keywords=keywords,
                query_tags=query_tags
            )
            
            if score > 0:
                scored_memories.append((memory, score))
        
        # 4. 점수 + 중요도 순 정렬
        scored_memories.sort(
            key=lambda x: (x[1], x[0].get("importance", 0)),
            reverse=True
        )
        
        # 5. 상위 N개 반환
        return [m for m, score in scored_memories[:limit]]
    
    def _calculate_relevance(
        self,
        memory: Dict,
        keywords: List[str],
        query_tags: List[str]
    ) -> float:
        """관련성 점수 계산
        
        점수 구성:
        - 내용 매칭: +3
        - 태그 매칭: +2 (per tag)
        - 중요도 보너스: +importance/10
        """
        score = 0.0
        content = memory.get("content", "").lower()
        tags = memory.get("tags", [])
        importance = memory.get("importance", 5)
        
        for keyword in keywords:
            if keyword and keyword.lower() in content:
                score += 3.0
            if keyword and keyword.lower() in [t.lower() for t in tags]:
                score += 2.0
        
        # 3. 중요도 보너스
        score += importance / 10.0
        
        return score
    
    def get_recent(
        self,
        player_id: str = "default",
        limit: int = 10
    ) -> List[Dict]:
        """최근 기억 반환"""
        player_memories = [
            m for m in self.memories
            if m.get("player_id") == player_id
        ]
        
        # 최신순 정렬
        player_memories.sort(
            key=lambda m: m.get("created_at", ""),
            reverse=True
        )
        
        return player_memories[:limit]

    def _is_duplicate(self, new_content: str) -> bool:
        """최근 기억 대비 중복 판단"""
        recent = self.memories[-10:]
        for memory in reversed(recent):
            old_content = memory.get("content", "")
            ratio = SequenceMatcher(None, new_content, old_content).ratio()
            if ratio > 0.95:
                logger.debug(f"Similar memory found: {ratio:.2f}")
                return True
        return False

    def summarize_old_memories(self, days_ago: int = 7) -> None:
        """오래된 중요 낮은 기억을 요약"""
        cutoff = datetime.now() - timedelta(days=days_ago)
        old_memories = [
            m for m in self.memories
            if datetime.fromisoformat(m["created_at"]) < cutoff
            and m.get("importance", 0) < 50
        ]
        if len(old_memories) < 10:
            return
        summary = self._create_summary(old_memories)
        for old in old_memories:
            self.memories.remove(old)

        summary_memory = {
            "id": uuid.uuid4().hex,
            "player_id": "summary",
            "content": f"[요약] {summary}",
            "emotion": "neutral",
            "importance": 30,
            "tags": ["summary"],
            "created_at": datetime.now().isoformat(),
        }
        self.memories.append(summary_memory)
        self._save()
        logger.info(f"Summarized {len(old_memories)} memories into one")

    def _create_summary(self, memories: List[Dict]) -> str:
        tag_counts: Dict[str, int] = {}
        for m in memories:
            for tag in m.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        summary_parts = [f"{tag} 관련 사건 {count}회" for tag, count in top_tags]
        return ", ".join(summary_parts)

    def print_memory_dashboard(self, player_id: str = "default") -> None:
        stats = self.get_stats(player_id)
        print("\n" + "="*60)
        print("📚 Memory Dashboard")
        print("="*60)
        print(f"Total Memories: {stats['total']}")
        print(f"Avg Importance: {stats['avg_importance']:.1f}/100")
        print("\nTop Characters:")
        npc_counts: Dict[str, int] = {}
        for memory in self.memories:
            for tag in memory.get("tags", []):
                if tag in ["lua", "bella", "elena", "sein", "roxanne", "leo"]:
                    npc_counts[tag] = npc_counts.get(tag, 0) + 1
        for npc, count in sorted(npc_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {npc}: {count} memories")
        print("\nTop Tags:")
        for tag, count in list(stats["top_tags"].items())[:10]:
            print(f"  {tag}: {count}")
        print("\nEmotions:")
        for emotion, count in stats["emotions"].items():
            print(f"  {emotion}: {count}")
        print("="*60 + "\n")
    
    def get_stats(self, player_id: str = "default") -> Dict:
        """통계 반환"""
        player_memories = [
            m for m in self.memories
            if m.get("player_id") == player_id
        ]
        
        if not player_memories:
            return {
                "total": 0,
                "avg_importance": 0,
                "emotions": {},
                "top_tags": {},
            }
        
        # 감정 분포
        emotions = {}
        for m in player_memories:
            emotion = m.get("emotion", "neutral")
            emotions[emotion] = emotions.get(emotion, 0) + 1
        
        # 태그 빈도
        tag_counts = {}
        for m in player_memories:
            for tag in m.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # 상위 태그
        top_tags = dict(sorted(
            tag_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10])
        
        return {
            "total": len(player_memories),
            "avg_importance": sum(m.get("importance", 0) for m in player_memories) / len(player_memories),
            "emotions": emotions,
            "top_tags": top_tags,
        }