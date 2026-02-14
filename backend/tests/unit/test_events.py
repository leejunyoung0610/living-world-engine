"""
EventManager 유닛 테스트
"""

import json
from pathlib import Path

import pytest

from backend.src.engine.events import EventManager


@pytest.fixture
def event_manager() -> EventManager:
    """기본 EventManager 픽스쳐"""
    em = EventManager()
    em.load_events([
        {
            "id": "test_var_event",
            "description": "변수 임계값 이벤트",
            "condition": {"type": "variable_threshold", "variable": "chaos_level", "op": ">=", "value": 0.5},
            "effects": [{"type": "world_variable", "key": "chaos_level", "change": -0.1}],
            "cooldown": 5,
            "tags": ["test"],
        },
        {
            "id": "test_turn_event",
            "description": "턴 범위 이벤트",
            "condition": {"type": "turn_range", "min_turn": 10, "max_turn": 20},
            "effects": [],
            "cooldown": 10,
            "tags": ["test"],
        },
        {
            "id": "test_rel_event",
            "description": "관계 임계값 이벤트",
            "condition": {"type": "relationship_threshold", "stat": "affection", "op": ">=", "value": 70},
            "effects": [],
            "cooldown": 15,
            "tags": ["romance"],
        },
    ])
    return em


@pytest.fixture
def snapshot_base() -> dict:
    """기본 스냅샷 (아무 조건도 충족 안 됨)"""
    return {
        "world": {"world_variables": {"chaos_level": 0.3, "rivalry_index": 0.2}},
        "player": {"relationships": {"elena": {"affection": 50, "trust": 30}}},
        "turn": 5,
        "day": 1,
    }


class TestLoadEvents:
    """이벤트 로딩 테스트"""

    def test_load_events_from_file(self, arcane_academy_path: Path) -> None:
        """실제 events.json 파일에서 로딩"""
        em = EventManager()
        em.load_events_from_file(arcane_academy_path / "events.json")
        assert len(em.event_templates) == 10

    def test_load_events_from_file_not_found(self, tmp_path: Path) -> None:
        """없는 파일 → FileNotFoundError"""
        em = EventManager()
        with pytest.raises(FileNotFoundError):
            em.load_events_from_file(tmp_path / "nope.json")

    def test_load_events_from_data(self) -> None:
        """리스트 데이터로 직접 로딩"""
        em = EventManager()
        em.load_events([{"id": "a"}, {"id": "b"}])
        assert len(em.event_templates) == 2


class TestCheckEvents:
    """조건 체크 테스트"""

    def test_no_match(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """아무 조건도 충족 안 됨 → 빈 리스트"""
        triggered = event_manager.check_events(snapshot_base)
        assert triggered == []

    def test_variable_threshold_match(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """world_variable 조건 충족"""
        snapshot_base["world"]["world_variables"]["chaos_level"] = 0.7
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_var_event" in ids

    def test_turn_range_match(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """턴 범위 조건 충족"""
        snapshot_base["turn"] = 15
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_turn_event" in ids

    def test_turn_range_outside(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """턴 범위 밖 → 트리거 안 됨"""
        snapshot_base["turn"] = 25
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_turn_event" not in ids

    def test_relationship_threshold_match(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """관계 수치 조건 충족"""
        snapshot_base["player"]["relationships"]["elena"]["affection"] = 80
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_rel_event" in ids

    def test_relationship_threshold_no_match(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """관계 수치 미달"""
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_rel_event" not in ids

    def test_cooldown_blocks_trigger(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """쿨다운 중인 이벤트는 트리거 안 됨"""
        snapshot_base["world"]["world_variables"]["chaos_level"] = 0.7
        event_manager.cooldowns["test_var_event"] = 3
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_var_event" not in ids

    def test_multiple_triggers(self, event_manager: EventManager, snapshot_base: dict) -> None:
        """여러 이벤트 동시 트리거"""
        snapshot_base["world"]["world_variables"]["chaos_level"] = 0.7
        snapshot_base["turn"] = 15
        triggered = event_manager.check_events(snapshot_base)
        ids = [e["id"] for e in triggered]
        assert "test_var_event" in ids
        assert "test_turn_event" in ids


class TestTriggerAndCooldown:
    """이벤트 발동 + 쿨다운 테스트"""

    def test_trigger_event_sets_cooldown(self, event_manager: EventManager) -> None:
        """이벤트 발동 → 쿨다운 설정"""
        event_manager.trigger_event("test_var_event")
        assert event_manager.cooldowns["test_var_event"] == 5

    def test_trigger_event_records_history(self, event_manager: EventManager) -> None:
        """이벤트 발동 → 히스토리에 기록"""
        event_manager.trigger_event("test_var_event")
        assert len(event_manager.triggered_events) == 1
        assert event_manager.triggered_events[0]["id"] == "test_var_event"

    def test_tick_cooldowns(self, event_manager: EventManager) -> None:
        """쿨다운 1턴 감소"""
        event_manager.cooldowns["test_var_event"] = 3
        event_manager.cooldowns["test_turn_event"] = 1
        event_manager.tick_cooldowns()
        assert event_manager.cooldowns["test_var_event"] == 2
        assert "test_turn_event" not in event_manager.cooldowns  # 만료됨

    def test_trigger_unknown_event(self, event_manager: EventManager) -> None:
        """없는 이벤트 발동 → 무시"""
        event_manager.trigger_event("nonexistent")
        assert len(event_manager.triggered_events) == 0
