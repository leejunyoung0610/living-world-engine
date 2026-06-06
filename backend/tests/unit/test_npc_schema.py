import pytest

from backend.src.schemas.npc import normalize_characters_for_storage, normalize_npc_record


def test_normalize_npc_minimal_name_only():
    n = normalize_npc_record({"name": "NPC1"}, 0)
    assert n["name"] == "NPC1"
    assert n["role"] == "등장인물"
    assert "id" in n


def test_normalize_npc_full_dialogue_fields():
    n = normalize_npc_record(
        {
            "id": "a",
            "name": "Kim",
            "role": "선배",
            "major": "무용과",
            "personality": "차분함",
            "background": "3학년",
            "speech_style": "존댓말",
        },
        0,
    )
    assert n["major"] == "무용과"
    assert n["speaking_style"] == "존댓말"
    assert "speech_style" not in n


def test_normalize_characters_payload():
    out = normalize_characters_for_storage(
        {
            "npcs": [{"name": "A", "role": "r"}],
            "player": {"name": "x"},
            "quests": [],
        }
    )
    assert "player" not in out
    assert len(out["npcs"]) == 1
    assert out["quests"] == []


def test_normalize_npc_relationship_stats():
    n = normalize_npc_record(
        {"name": "X", "relationship_stats": {"affection": 80, "disgust": 2}},
        0,
    )
    assert n["relationship_stats"] == {"affection": 80, "disgust": 2}


def test_normalize_npc_requires_name():
    with pytest.raises(ValueError, match="name is required"):
        normalize_npc_record({"role": "x"}, 0)
