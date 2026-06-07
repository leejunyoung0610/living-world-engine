"""LLM 자원 스탯 → EventCard 합성."""

from backend.src.engine.llm_stat_events import build_llm_stat_event


class TestBuildLlmStatEvent:
    def test_skips_small_delta_without_show_card(self) -> None:
        assert build_llm_stat_event(3, [{"key": "rap", "change": 2, "before": 5, "after": 7}]) is None

    def test_builds_card_when_delta_ge_3(self) -> None:
        ev = build_llm_stat_event(
            5,
            [{"key": "rap", "change": 4, "before": 10, "after": 14, "reason": "랩 연습"}],
        )
        assert ev is not None
        assert ev["event_id"] == "llm_stat_turn_5"
        assert ev["name"] == "능력 변화"
        assert ev["description"] == "랩 연습"
        assert len(ev["applied_effects"]) == 1
        assert ev["applied_effects"][0]["change"] == 4

    def test_show_card_forces_small_delta(self) -> None:
        ev = build_llm_stat_event(
            2,
            [{"key": "skill", "change": 1, "before": 0, "after": 1, "show_card": True}],
        )
        assert ev is not None
        assert len(ev["applied_effects"]) == 1

    def test_combines_multiple_stats_one_card(self) -> None:
        ev = build_llm_stat_event(
            7,
            [
                {"key": "rap", "change": 3, "before": 1, "after": 4},
                {"key": "producing", "change": -3, "before": 10, "after": 7, "reason": "피로"},
            ],
        )
        assert ev is not None
        assert len(ev["applied_effects"]) == 2
