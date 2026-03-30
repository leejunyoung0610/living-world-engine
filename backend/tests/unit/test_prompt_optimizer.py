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

    # 공통 코어만 (Sonnet 경로) — 슬림 유지
    assert len(prompt) < 3500, f"Prompt too long: {len(prompt)} chars"
    assert "[Haiku·경량 모델 전용" not in prompt


def test_no_haiku_supplement_in_prompt():
    """Sonnet 단일 경로 — Haiku 전용 접두 없음"""
    optimizer = SystemPromptOptimizer()
    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test World"},
        player={"turn": 1, "name": "P", "location": "x"},
        active_location="x",
        npcs=[],
        memories=[],
    )
    assert "[Haiku·경량 모델 전용" not in prompt
    assert "너는 Test World" in prompt
    assert len(prompt) < 4500


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


def test_build_system_blocks_split_for_cache():
    """static / dynamic 분리 — dynamic에만 상황·NPC·기억"""
    optimizer = SystemPromptOptimizer()
    memories = [{"content": "Secret", "importance": 8}]
    npcs = [
        {
            "id": "n1",
            "name": "OnlyHere",
            "location": "A",
            "role": "R",
            "persona": {"traits": ["t"]},
        }
    ]
    static, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"turn": 2, "name": "P", "location": "A"},
        active_location="A",
        npcs=npcs,
        memories=memories,
    )
    assert "## 현재 상황" in dynamic
    assert "OnlyHere" in dynamic
    assert "Secret" in dynamic
    assert "## 현재 상황" not in static
    assert "OnlyHere" not in static
    assert "## Tool (update_game_state)" in static
    assert "## 응답 규칙" in static


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
