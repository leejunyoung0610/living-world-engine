"""
EventManager 유닛 테스트
"""

from pathlib import Path

import pytest

from backend.src.engine.events import EventManager
from backend.src.engine.state import WorldState


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


class TestRelationshipThresholdNpcId:
    """``relationship_threshold`` + 선택적 ``npc_id``."""

    def test_without_npc_id_any_npc_still_works(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "any_npc",
            "condition": {"type": "relationship_threshold", "stat": "affection", "op": ">=", "value": 40},
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {}, "relationships": {
            "npc_a": {"affection": 10},
            "npc_b": {"affection": 45},
        }})
        assert [e["id"] for e in em.check_events(snap)] == ["any_npc"]

    def test_with_npc_id_only_that_npc(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "ahyeon_only",
            "condition": {
                "type": "relationship_threshold",
                "npc_id": "world_1780761374",
                "stat": "affection",
                "op": ">=",
                "value": 40,
            },
            "cooldown": 999,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {}, "relationships": {
            "world_1780761374": {"affection": 39},
            "world_1780761374_2": {"affection": 80},
        }})
        assert em.check_events(snap) == []

        snap["player"]["relationships"]["world_1780761374"]["affection"] = 40
        assert [e["id"] for e in em.check_events(snap)] == ["ahyeon_only"]

    def test_unknown_npc_id_returns_false(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "missing_npc",
            "condition": {
                "type": "relationship_threshold",
                "npc_id": "does_not_exist",
                "stat": "affection",
                "op": ">=",
                "value": 1,
            },
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {}, "relationships": {
            "elena": {"affection": 99},
        }})
        assert em.check_events(snap) == []


class TestOnceFlag:
    """``once: true`` 이벤트는 이미 발동한 ID는 재트리거하지 않음."""

    def test_once_skips_after_trigger(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "milestone",
            "once": True,
            "condition": {"type": "turn_range", "min_turn": 0, "max_turn": 99},
            "cooldown": 999,
        }])
        snap = _snap_with(turn=5)
        assert [e["id"] for e in em.check_events(snap)] == ["milestone"]
        em.trigger_event("milestone")
        assert em.check_events(snap) == []

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


# ── PR-1: 자원 스탯/플래그/시간/복합 조건 + 효과 적용 ────────────────────────


@pytest.fixture
def stats_world_state() -> WorldState:
    """자원 스탯 clamp 검증을 위해 ``stats_schema.resource`` 가 있는 월드."""
    state = WorldState()
    state.world = {
        "id": "test",
        "name": "test",
        "stats_schema": {
            "resource": {
                "hp": {"min": 0, "max": 100, "default": 80, "label": "체력"},
                "stress": {"min": 0, "max": 10, "default": 0, "label": "스트레스"},
                "focus": {"min": 0, "max": 10, "default": 5, "label": "집중력"},
            }
        },
    }
    state.player = {
        "name": "Tester",
        "class": "campus_resident",
        "stats": {"hp": 80, "stress": 0, "focus": 5},
        "flags": {"warned_burnout": False},
        "relationships": {},
    }
    state.npcs = []
    return state


def _snap_with(player: dict | None = None, world: dict | None = None, **kw) -> dict:
    return {
        "world": world or {"world_variables": {}},
        "player": player or {"stats": {}, "flags": {}, "relationships": {}},
        "turn": kw.get("turn", 0),
        "day": kw.get("day", 1),
        **{k: v for k, v in kw.items() if k not in ("turn", "day")},
    }


class TestResourceStatThreshold:
    """`resource_stat_threshold` 조건 — `player.stats[key]` 비교."""

    def test_match_exact(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "burnout",
            "condition": {"type": "resource_stat_threshold", "stat": "stress", "op": ">=", "value": 8},
            "cooldown": 5,
        }])
        snap = _snap_with(player={"stats": {"stress": 8}, "flags": {}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["burnout"]

    def test_no_match_below(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "burnout",
            "condition": {"type": "resource_stat_threshold", "stat": "stress", "op": ">=", "value": 8},
            "cooldown": 5,
        }])
        snap = _snap_with(player={"stats": {"stress": 7}, "flags": {}, "relationships": {}})
        assert em.check_events(snap) == []

    def test_missing_stat_treated_as_zero(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "needs_focus",
            "condition": {"type": "resource_stat_threshold", "stat": "focus", "op": "<=", "value": 1},
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["needs_focus"]


class TestFlagCondition:
    def test_equals_match(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "after_intro",
            "condition": {"type": "flag", "key": "tutorial_done", "equals": True},
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {"tutorial_done": True}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["after_intro"]

    def test_equals_string(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "in_book_club",
            "condition": {"type": "flag", "key": "club", "equals": "독서회"},
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {"club": "독서회"}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["in_book_club"]

    def test_no_match_when_value_differs(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "after_intro",
            "condition": {"type": "flag", "key": "tutorial_done", "equals": True},
            "cooldown": 1,
        }])
        snap = _snap_with(player={"stats": {}, "flags": {"tutorial_done": False}, "relationships": {}})
        assert em.check_events(snap) == []


class TestTimeWindow:
    def test_min_max_day_inclusive(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "midterm_week",
            "condition": {"type": "time_window", "min_day": 5, "max_day": 7},
            "cooldown": 1,
        }])
        for day, expected in [(4, []), (5, ["midterm_week"]), (7, ["midterm_week"]), (8, [])]:
            snap = _snap_with(day=day)
            assert [e["id"] for e in em.check_events(snap)] == expected

    def test_phase_inferred_from_turn_when_state_phase_absent(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "night_event",
            "condition": {"type": "time_window", "phase": "night"},
            "cooldown": 1,
        }])
        # 짝수 turn → day, 홀수 → night
        assert [e["id"] for e in em.check_events(_snap_with(turn=4))] == []
        assert [e["id"] for e in em.check_events(_snap_with(turn=5))] == ["night_event"]


class TestCompoundRelationship:
    """동일 NPC에 관계 조건 2개 (compound AND)."""

    def test_two_relationship_stats_same_npc(self) -> None:
        em = EventManager()
        npc_id = "npc_ahyeon"
        em.load_events([{
            "id": "deep_bond",
            "condition": {
                "type": "compound",
                "op": "and",
                "conditions": [
                    {
                        "type": "relationship_threshold",
                        "npc_id": npc_id,
                        "stat": "affection",
                        "op": ">=",
                        "value": 50,
                    },
                    {
                        "type": "relationship_threshold",
                        "npc_id": npc_id,
                        "stat": "trust",
                        "op": ">=",
                        "value": 40,
                    },
                ],
            },
            "cooldown": 999,
            "once": True,
        }])
        snap = _snap_with(
            player={
                "stats": {},
                "flags": {},
                "relationships": {
                    npc_id: {"affection": 55, "trust": 45},
                },
            },
        )
        assert [e["id"] for e in em.check_events(snap)] == ["deep_bond"]

        snap_fail = _snap_with(
            player={
                "stats": {},
                "flags": {},
                "relationships": {
                    npc_id: {"affection": 55, "trust": 30},
                },
            },
        )
        assert em.check_events(snap_fail) == []


class TestCompound:
    def test_and_all_must_match(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "burnout_warning",
            "condition": {
                "type": "compound", "op": "and",
                "conditions": [
                    {"type": "resource_stat_threshold", "stat": "stress", "op": ">=", "value": 8},
                    {"type": "flag", "key": "warned_burnout", "equals": False},
                ],
            },
            "cooldown": 12,
        }])
        snap = _snap_with(player={"stats": {"stress": 9}, "flags": {"warned_burnout": False}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["burnout_warning"]
        snap2 = _snap_with(player={"stats": {"stress": 9}, "flags": {"warned_burnout": True}, "relationships": {}})
        assert em.check_events(snap2) == []

    def test_or_any_match(self) -> None:
        em = EventManager()
        em.load_events([{
            "id": "rest_needed",
            "condition": {
                "type": "compound", "op": "or",
                "conditions": [
                    {"type": "resource_stat_threshold", "stat": "stress", "op": ">=", "value": 8},
                    {"type": "resource_stat_threshold", "stat": "hp", "op": "<=", "value": 30},
                ],
            },
            "cooldown": 5,
        }])
        snap = _snap_with(player={"stats": {"stress": 1, "hp": 20}, "flags": {}, "relationships": {}})
        assert [e["id"] for e in em.check_events(snap)] == ["rest_needed"]


class TestPriorityOrdering:
    def test_higher_priority_first(self) -> None:
        em = EventManager()
        em.load_events([
            {"id": "low", "condition": {"type": "turn_range", "min_turn": 0, "max_turn": 99}, "priority": 1, "cooldown": 5},
            {"id": "high", "condition": {"type": "turn_range", "min_turn": 0, "max_turn": 99}, "priority": 9, "cooldown": 5},
            {"id": "mid", "condition": {"type": "turn_range", "min_turn": 0, "max_turn": 99}, "priority": 5, "cooldown": 5},
        ])
        ids = [e["id"] for e in em.check_events(_snap_with(turn=3))]
        assert ids == ["high", "mid", "low"]


class TestApplyEffects:
    def test_resource_stat_increase_with_clamp(self, stats_world_state: WorldState) -> None:
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "resource_stat", "key": "stress", "change": 5}],
        )
        assert stats_world_state.player["stats"]["stress"] == 5
        assert applied == [
            {"type": "resource_stat", "key": "stress", "change": 5, "before": 0, "after": 5}
        ]

    def test_resource_stat_clamps_to_max(self, stats_world_state: WorldState) -> None:
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "resource_stat", "key": "stress", "change": 99}],
        )
        assert stats_world_state.player["stats"]["stress"] == 10
        assert applied[0]["after"] == 10

    def test_resource_stat_clamps_to_min(self, stats_world_state: WorldState) -> None:
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "resource_stat", "key": "hp", "change": -999}],
        )
        assert stats_world_state.player["stats"]["hp"] == 0
        assert applied[0]["after"] == 0

    def test_flag_set_records_before_and_after(self, stats_world_state: WorldState) -> None:
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "flag_set", "key": "warned_burnout", "value": True}],
        )
        assert stats_world_state.player["flags"]["warned_burnout"] is True
        assert applied == [
            {"type": "flag_set", "key": "warned_burnout", "before": False, "after": True}
        ]

    def test_narrative_does_not_change_state(self, stats_world_state: WorldState) -> None:
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "narrative", "text": "거울 속 얼굴이 낯설다."}],
        )
        assert stats_world_state.player["stats"] == {"hp": 80, "stress": 0, "focus": 5}
        assert applied == [{"type": "narrative", "text": "거울 속 얼굴이 낯설다."}]

    def test_relationship_effect_is_ignored_in_pr1(self, stats_world_state: WorldState) -> None:
        """PR-1 에서 relationship 효과는 의도적으로 미지원 — 조용히 무시.
        감정·관계는 LLM 의 이야기 흐름이 ``update_relationship`` 으로만 변동시킨다.
        """
        em = EventManager()
        before = dict(stats_world_state.player.get("relationships", {}))
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "relationship", "npc_id": "elena", "stat": "affection", "change": 5}],
        )
        assert stats_world_state.player["relationships"] == before
        assert applied == []

    def test_player_stat_alias_still_works(self, stats_world_state: WorldState) -> None:
        """호환 — 구 ``player_stat`` 이름의 효과도 동일하게 처리."""
        em = EventManager()
        applied = em.apply_effects(
            stats_world_state,
            [{"type": "player_stat", "key": "focus", "change": -2}],
        )
        assert stats_world_state.player["stats"]["focus"] == 3
        assert applied[0]["type"] == "resource_stat"
        assert applied[0]["after"] == 3
