import pytest

from backend.src.engine.prompt_optimizer import SystemPromptOptimizer


def test_prompt_length():
    """프롬프트 길이가 목표 범위 안인지"""
    optimizer = SystemPromptOptimizer()

    world = {"name": "Test World"}
    player = {"turn": 1, "location": "test_area"}
    npcs = [
        {
            "id": "npc1",
            "name": "Test NPC",
            "role": "Tester",
            "location": "test_area",
            "persona": {"traits": ["friendly", "helpful", "test"]},
        }
    ]
    memories = [{"content": "Test memory", "importance": 7}]

    prompt = optimizer.build_optimized_prompt(
        world=world,
        player=player,
        active_location="test_area",
        npcs=npcs,
        memories=memories,
    )

    assert len(prompt) < 2000, f"Prompt too long: {len(prompt)} chars"


def test_only_active_location_npcs():
    """현재 위치 NPC만 포함되는지"""
    optimizer = SystemPromptOptimizer()

    npcs = [
        {"id": "npc1", "name": "Here", "location": "area1", "role": "Test", "persona": {"traits": []}},
        {"id": "npc2", "name": "There", "location": "area2", "role": "Test", "persona": {"traits": []}},
    ]

    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test"},
        player={"turn": 1, "location": "area1"},
        active_location="area1",
        npcs=npcs,
        memories=[],
    )

    assert "Here" in prompt
    assert "There" not in prompt


def test_only_important_memories():
    """중요 기억만 포함되는지"""
    optimizer = SystemPromptOptimizer()

    memories = [
        {"content": "Low importance", "importance": 3},
        {"content": "High importance", "importance": 8},
    ]

    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test"},
        player={"turn": 1, "location": "area1"},
        active_location="area1",
        npcs=[],
        memories=memories,
    )

    assert "High importance" in prompt
    assert "Low importance" not in prompt
