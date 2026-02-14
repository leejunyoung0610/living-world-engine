"""
GameEngine ↔ EventManager 연동 유닛 테스트 (LLM Mock)
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.src.engine.game_loop import GameEngine


@pytest.fixture
def mock_engine():
    """LLM을 Mock한 GameEngine — API 호출 없이 이벤트 연동 테스트"""
    with patch("backend.src.engine.game_loop.ClaudeClient") as mock_llm_cls:
        engine = GameEngine()
        # LLM Mock: 항상 텍스트 응답 반환
        engine.llm.process_turn = MagicMock(return_value={
            "response": "테스트 응답입니다.",
            "state_changes": {},
            "tool_used": False,
        })

        # 간단한 상태 설정
        engine.state.world = {
            "id": "test",
            "name": "Test World",
            "world_variables": {"chaos_level": 0.3, "rivalry_index": 0.2},
        }
        engine.state.player = {
            "name": "Tester",
            "class": "전사",
            "stats": {},
            "flags": {},
            "relationships": {"elena": {"affection": 50, "trust": 30}},
        }
        engine.state.npcs = [
            {"id": "elena", "name": "엘레나", "role": "수석", "location": "결투장"},
        ]

        # 이벤트 로딩
        engine.event_manager.load_events([
            {
                "id": "chaos_event",
                "description": "혼돈 이벤트",
                "narrative_hint": "혼돈이 커지고 있다.",
                "condition": {"type": "variable_threshold", "variable": "chaos_level", "op": ">=", "value": 0.5},
                "effects": [],
                "cooldown": 5,
            },
            {
                "id": "love_event",
                "description": "호감 이벤트",
                "narrative_hint": "누군가가 마음을 열기 시작한다.",
                "condition": {"type": "relationship_threshold", "stat": "affection", "op": ">=", "value": 80},
                "effects": [],
                "cooldown": 15,
            },
            {
                "id": "turn_event",
                "description": "턴 이벤트",
                "narrative_hint": "시간이 흐르고 있다.",
                "condition": {"type": "turn_range", "min_turn": 3, "max_turn": 10},
                "effects": [],
                "cooldown": 5,
            },
        ])
        engine.validator.set_valid_characters(["엘레나"])
        return engine


class TestGameEngineEventIntegration:
    """GameEngine에서 이벤트가 정상 트리거되는지"""

    def test_no_events_when_conditions_not_met(self, mock_engine: GameEngine) -> None:
        """조건 불충족 → 이벤트 없음"""
        result = mock_engine.process_turn("안녕")
        assert result["events_triggered"] == []

    def test_event_triggered_when_variable_condition_met(self, mock_engine: GameEngine) -> None:
        """world_variable 조건 충족 → 이벤트 트리거"""
        mock_engine.state.world["world_variables"]["chaos_level"] = 0.7
        result = mock_engine.process_turn("안녕")

        ids = [e["event_id"] for e in result["events_triggered"]]
        assert "chaos_event" in ids

    def test_event_triggered_when_relationship_condition_met(self, mock_engine: GameEngine) -> None:
        """관계 수치 조건 충족 → 이벤트 트리거"""
        mock_engine.state.player["relationships"]["elena"]["affection"] = 85
        result = mock_engine.process_turn("안녕")

        ids = [e["event_id"] for e in result["events_triggered"]]
        assert "love_event" in ids

    def test_cooldown_prevents_retrigger(self, mock_engine: GameEngine) -> None:
        """이벤트 1회 발생 후 쿨다운으로 재발생 차단"""
        mock_engine.state.world["world_variables"]["chaos_level"] = 0.7

        result1 = mock_engine.process_turn("1턴째")
        assert any(e["event_id"] == "chaos_event" for e in result1["events_triggered"])

        result2 = mock_engine.process_turn("2턴째")
        assert not any(e["event_id"] == "chaos_event" for e in result2["events_triggered"])

    def test_multiple_events_trigger(self, mock_engine: GameEngine) -> None:
        """여러 조건 동시 충족 → 여러 이벤트 트리거"""
        mock_engine.state.world["world_variables"]["chaos_level"] = 0.7
        mock_engine.state.player["relationships"]["elena"]["affection"] = 90
        # turn을 3으로 만들기 위해 미리 진행
        mock_engine.state.turn = 2  # process_turn에서 advance_turn → 3

        result = mock_engine.process_turn("안녕")
        ids = [e["event_id"] for e in result["events_triggered"]]
        assert "chaos_event" in ids
        assert "love_event" in ids
        assert "turn_event" in ids

    def test_triggered_event_includes_narrative_hint(self, mock_engine: GameEngine) -> None:
        """트리거된 이벤트에 narrative_hint 포함"""
        mock_engine.state.world["world_variables"]["chaos_level"] = 0.7
        result = mock_engine.process_turn("안녕")

        event = result["events_triggered"][0]
        assert event["narrative_hint"] == "혼돈이 커지고 있다."

    def test_events_loaded_on_initialize(self) -> None:
        """initialize() 시 events.json 자동 로딩"""
        with patch("backend.src.engine.game_loop.ClaudeClient"):
            engine = GameEngine()
            engine.initialize("backend/src/worlds/arcane_academy")
            assert len(engine.event_manager.event_templates) == 10
