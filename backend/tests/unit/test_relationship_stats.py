"""플랫폼 고정 관계 스탯 정의."""

from backend.src.engine.llm import GAME_STATE_TOOL
from backend.src.engine.relationship_stats import (
    RELATIONSHIP_STAT_LABELS_KO,
    RELATIONSHIP_STAT_ORDER,
    VALID_RELATIONSHIP_STATS,
)
from backend.src.engine.validator import StateChangeValidator


def test_eight_stats_include_wrath() -> None:
    assert "disgust" in VALID_RELATIONSHIP_STATS
    assert "wrath" in VALID_RELATIONSHIP_STATS
    assert len(RELATIONSHIP_STAT_ORDER) == 8
    assert RELATIONSHIP_STAT_LABELS_KO["disgust"] == "혐오"
    assert RELATIONSHIP_STAT_LABELS_KO["wrath"] == "살의"


def test_llm_tool_enum_matches_platform_stats() -> None:
    stat_schema = GAME_STATE_TOOL["input_schema"]["properties"]["relationship_changes"]["items"][
        "properties"
    ]["stat"]
    assert stat_schema["enum"] == list(RELATIONSHIP_STAT_ORDER)


def test_validator_accepts_all_platform_stats() -> None:
    v = StateChangeValidator(valid_characters=[])
    for stat in RELATIONSHIP_STAT_ORDER:
        result = v.validate(
            {"relationship_changes": [{"character": "NPC", "stat": stat, "change": 1, "reason": "테스트 상호작용"}]}
        )
        assert len(result["relationship_changes"]) == 1
