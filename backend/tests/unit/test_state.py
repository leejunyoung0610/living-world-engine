"""
WorldState 유닛 테스트
"""

import json
from pathlib import Path

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


class TestLoadFromFile:
    """WorldState.load_from_file 클래스 메서드 테스트"""

    def test_load_from_file_success(self, arcane_academy_path: Path) -> None:
        """정상 로딩: 실제 세계관 JSON 파일에서 WorldState 생성"""
        world_json = arcane_academy_path / "world.json"
        characters_json = arcane_academy_path / "characters.json"

        state = WorldState.load_from_file(world_json, characters_json)

        # world.json 데이터 확인
        assert state.world["id"] == "arcane_academy"
        assert state.world["name"] == "아케인 아카데미"
        assert "world_variables" in state.world
        assert state.world["world_variables"]["chaos_level"] == 0.33

        # characters.json - player 데이터 확인
        assert state.player["name"] == "Guest"
        assert state.player["class"] == "정크"
        assert state.player["stats"]["hp"] == 24

        # characters.json - NPC 데이터 확인
        assert len(state.npcs) == 6
        elena = state.get_npc("elena")
        assert elena is not None
        assert elena["name"] == "엘레나"

        # 초기 상태 확인
        assert state.turn == 0
        assert state.day == 1
        assert state.memories == []

    def test_load_from_dicts_matches_file_load(self, arcane_academy_path: Path) -> None:
        world_json = arcane_academy_path / "world.json"
        characters_json = arcane_academy_path / "characters.json"
        with open(world_json, encoding="utf-8") as f:
            w = json.load(f)
        with open(characters_json, encoding="utf-8") as f:
            c = json.load(f)
        state = WorldState.load_from_dicts(w, c)
        assert state.world["id"] == "arcane_academy"
        assert len(state.npcs) == 6

    def test_load_from_file_not_found(self, tmp_path: Path) -> None:
        """파일 없음: FileNotFoundError와 명확한 메시지"""
        fake_world = tmp_path / "nonexistent_world.json"
        fake_chars = tmp_path / "nonexistent_chars.json"

        with pytest.raises(FileNotFoundError, match="nonexistent_world.json"):
            WorldState.load_from_file(fake_world, fake_chars)

        # world.json은 있고 characters.json만 없는 경우
        real_world = tmp_path / "world.json"
        real_world.write_text(
            json.dumps({"id": "test", "name": "Test World"}, ensure_ascii=False),
            encoding="utf-8",
        )

        with pytest.raises(FileNotFoundError, match="nonexistent_chars.json"):
            WorldState.load_from_file(real_world, fake_chars)

    def test_load_from_file_invalid_json(self, tmp_path: Path) -> None:
        """잘못된 JSON: JSONDecodeError와 파일명 포함 메시지"""
        bad_world = tmp_path / "bad_world.json"
        bad_world.write_text("{invalid json content!!!", encoding="utf-8")
        good_chars = tmp_path / "characters.json"
        good_chars.write_text(
            json.dumps({"player": {}, "npcs": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        with pytest.raises(json.JSONDecodeError):
            WorldState.load_from_file(bad_world, good_chars)

        # characters.json이 잘못된 경우
        good_world = tmp_path / "world.json"
        good_world.write_text(
            json.dumps({"id": "test", "name": "Test World"}, ensure_ascii=False),
            encoding="utf-8",
        )
        bad_chars = tmp_path / "bad_chars.json"
        bad_chars.write_text("not a json file", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            WorldState.load_from_file(good_world, bad_chars)

    def test_load_from_file_missing_fields(self, tmp_path: Path) -> None:
        """필수 필드 누락: ValueError와 누락 필드명"""
        # world.json에 "id" 없음
        world_no_id = tmp_path / "world.json"
        world_no_id.write_text(
            json.dumps({"name": "Test World"}, ensure_ascii=False),
            encoding="utf-8",
        )
        chars = tmp_path / "characters.json"
        chars.write_text(
            json.dumps({"player": {"name": "P"}, "npcs": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="id"):
            WorldState.load_from_file(world_no_id, chars)

        # world.json에 "name" 없음
        world_no_name = tmp_path / "world2.json"
        world_no_name.write_text(
            json.dumps({"id": "test"}, ensure_ascii=False),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="name"):
            WorldState.load_from_file(world_no_name, chars)

        # characters.json에 "npcs" 없음
        good_world = tmp_path / "world3.json"
        good_world.write_text(
            json.dumps({"id": "test", "name": "Test"}, ensure_ascii=False),
            encoding="utf-8",
        )
        chars_no_npcs = tmp_path / "chars_no_npcs.json"
        chars_no_npcs.write_text(
            json.dumps({"player": {"name": "P"}}, ensure_ascii=False),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="npcs"):
            WorldState.load_from_file(good_world, chars_no_npcs)

    def test_load_multiple_characters(self, tmp_path: Path) -> None:
        """여러 NPC 로딩: 각 NPC 데이터가 정확한지"""
        world_file = tmp_path / "world.json"
        world_file.write_text(
            json.dumps(
                {"id": "multi-test", "name": "Multi World", "regions": ["A", "B"]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        npcs_data = [
            {"id": "npc1", "name": "NPC-일", "role": "전사", "location": "A"},
            {"id": "npc2", "name": "NPC-이", "role": "마법사", "location": "B"},
            {"id": "npc3", "name": "NPC-삼", "role": "도적", "location": "A"},
        ]
        chars_file = tmp_path / "characters.json"
        chars_file.write_text(
            json.dumps(
                {"player": {"name": "Hero", "class": "용사"}, "npcs": npcs_data},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        state = WorldState.load_from_file(world_file, chars_file)

        # NPC 개수
        assert len(state.npcs) == 3

        # 각 NPC 정확성
        assert state.get_npc("npc1")["name"] == "NPC-일"
        assert state.get_npc("npc2")["role"] == "마법사"
        assert state.get_npc("npc3")["location"] == "A"

        # 이름으로도 조회 가능
        names = state.get_all_character_names()
        assert "NPC-일" in names
        assert "NPC-이" in names
        assert "NPC-삼" in names

        # player 데이터
        assert state.player["name"] == "Hero"
        assert state.player["class"] == "용사"
