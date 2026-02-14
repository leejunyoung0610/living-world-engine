"""
WorldState 유닛 테스트
"""

import pytest

from backend.src.engine.state import WorldState


class TestWorldState:
    """WorldState 클래스 테스트"""

    def test_get_npc_by_id(self, world_state: WorldState) -> None:
        """NPC ID로 조회"""
        npc = world_state.get_npc("elena")
        assert npc is not None
        assert npc["name"] == "엘레나"

    def test_get_npc_by_name(self, world_state: WorldState) -> None:
        """NPC 이름으로 조회"""
        npc = world_state.get_npc_by_name("벨라")
        assert npc is not None
        assert npc["id"] == "bella"

    def test_get_npc_not_found(self, world_state: WorldState) -> None:
        """존재하지 않는 NPC 조회 시 None 반환"""
        assert world_state.get_npc("nonexistent") is None
        assert world_state.get_npc_by_name("없는캐릭터") is None

    def test_get_all_character_names(self, world_state: WorldState) -> None:
        """모든 캐릭터 이름 조회"""
        names = world_state.get_all_character_names()
        assert "엘레나" in names
        assert "벨라" in names
        assert "루아" in names

    def test_get_relationship(self, world_state: WorldState) -> None:
        """관계 수치 조회"""
        assert world_state.get_relationship("elena", "affection") == 50
        assert world_state.get_relationship("elena", "trust") == 30

    def test_get_relationship_default(self, world_state: WorldState) -> None:
        """존재하지 않는 관계 수치는 기본값 50"""
        assert world_state.get_relationship("elena", "respect") == 50
        assert world_state.get_relationship("unknown_npc", "affection") == 50

    def test_update_relationship(self, world_state: WorldState) -> None:
        """관계 수치 업데이트"""
        new_val = world_state.update_relationship("elena", "affection", 10)
        assert new_val == 60
        assert world_state.get_relationship("elena", "affection") == 60

    def test_relationship_clamping_upper(self, world_state: WorldState) -> None:
        """관계 수치 상한 (100) 제한"""
        # 현재 50 + 200 = 250 → 100으로 클램핑
        new_val = world_state.update_relationship("elena", "affection", 200)
        assert new_val == 100

    def test_relationship_clamping_lower(self, world_state: WorldState) -> None:
        """관계 수치 하한 (0) 제한"""
        # 현재 50 - 200 = -150 → 0으로 클램핑
        new_val = world_state.update_relationship("elena", "affection", -200)
        assert new_val == 0

    def test_apply_changes_relationship(self, world_state: WorldState) -> None:
        """상태 변경 적용 - 관계"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 10},
            ],
            "new_memories": [],
        }
        applied = world_state.apply_changes(changes)
        assert len(applied["relationship_changes"]) == 1
        assert applied["relationship_changes"][0]["new_value"] == 60

    def test_apply_changes_invalid_character(self, world_state: WorldState) -> None:
        """존재하지 않는 캐릭터 변경은 무시"""
        changes = {
            "relationship_changes": [
                {"character": "없는캐릭터", "stat": "affection", "change": 10},
            ],
            "new_memories": [],
        }
        applied = world_state.apply_changes(changes)
        assert len(applied["relationship_changes"]) == 0

    def test_apply_changes_memories(self, world_state: WorldState) -> None:
        """상태 변경 적용 - 기억"""
        changes = {
            "relationship_changes": [],
            "new_memories": [
                {"content": "테스트 기억", "emotion": "joy", "importance": 7},
            ],
        }
        applied = world_state.apply_changes(changes)
        assert len(applied["memories_added"]) == 1
        assert len(world_state.memories) == 1

    def test_advance_turn(self, world_state: WorldState) -> None:
        """턴 진행"""
        assert world_state.turn == 0
        assert world_state.day == 1

        for _ in range(5):
            world_state.advance_turn()

        assert world_state.turn == 5
        assert world_state.day == 2  # 5턴마다 하루 경과

    def test_snapshot(self, world_state: WorldState) -> None:
        """스냅샷 생성"""
        snapshot = world_state.snapshot()
        assert snapshot["player"]["name"] == "TestPlayer"
        assert len(snapshot["npcs"]) == 3
        assert snapshot["turn"] == 0
