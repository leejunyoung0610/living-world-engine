"""NPC 관계 프로필 · 플레이 시드 · 적용 필터."""

from backend.src.engine.relationship_stats import (
    build_session_relationship_view,
    npc_relationship_profile,
    seed_player_relationships_from_npcs,
)
from backend.src.engine.state import WorldState
from backend.src.schemas.npc import normalize_npc_record


def test_normalize_npc_relationship_stats() -> None:
    n = normalize_npc_record(
        {
            "name": "A",
            "relationship_stats": {"affection": 70, "disgust": 5, "invalid": 99},
        },
        0,
    )
    assert n["relationship_stats"] == {"affection": 70, "disgust": 5}


def test_seed_player_relationships_from_npcs() -> None:
    player: dict = {"name": "P"}
    npcs = [
        {
            "id": "elena",
            "name": "엘레나",
            "relationship_stats": {"affection": 20, "trust": 10},
        },
        {"id": "bella", "name": "벨라"},
    ]
    seed_player_relationships_from_npcs(player, npcs)
    assert player["relationships"]["elena"] == {"affection": 20, "trust": 10}
    assert "bella" not in player["relationships"]


def test_apply_changes_skips_disabled_stat() -> None:
    state = WorldState()
    state.npcs = [
        {
            "id": "elena",
            "name": "엘레나",
            "relationship_stats": {"affection": 50},
        }
    ]
    state.player = {"name": "P", "relationships": {"elena": {"affection": 50}}}
    applied = state.apply_changes(
        {
            "relationship_changes": [
                {"character": "엘레나", "stat": "trust", "change": 2, "reason": "신뢰가 쌓였다"},
                {"character": "엘레나", "stat": "affection", "change": 2, "reason": "호감이 올랐다"},
            ],
        }
    )
    assert len(applied["relationship_changes"]) == 1
    assert applied["relationship_changes"][0]["stat"] == "affection"
    assert state.player["relationships"]["elena"]["affection"] == 52
    assert "trust" not in state.player["relationships"]["elena"]


def test_build_session_relationship_view() -> None:
    npcs = [{"id": "n1", "name": "Kim", "relationship_stats": {"affection": 40}}]
    player = {"relationships": {"n1": {"affection": 55}}}
    rows = build_session_relationship_view(npcs, player)
    assert len(rows) == 1
    assert rows[0]["npc_name"] == "Kim"
    assert rows[0]["stats"] == {"affection": 55}


def test_legacy_initial_stats_maps_to_profile() -> None:
    profile = npc_relationship_profile(
        {"id": "x", "initial_stats": {"trust": 30, "romance": 0}}
    )
    assert profile == {"trust": 30, "romance": 0}
