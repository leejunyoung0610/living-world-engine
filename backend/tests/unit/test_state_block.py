"""State 블록 — 확정 플래그·일차 · dynamic 상단 삽입."""

from backend.src.engine.prompt_optimizer import SystemPromptOptimizer
from backend.src.engine.state_block import build_state_block


def test_build_state_block_day_only_without_flags() -> None:
    block = build_state_block(player={"relationships": {}}, day=13)
    assert "## 지금 사실" in block
    assert "13일차" in block
    assert ": 연인" not in block
    assert "수치만으로" in block


def test_build_state_block_shows_truthy_flags() -> None:
    block = build_state_block(
        player={
            "flags": {
                "dating_ahyun": True,
                "warned_burnout": False,
                "current_location": "인천 원룸",
            }
        },
        day=5,
    )
    assert "확정: dating_ahyun" in block
    assert "확정: current_location = 인천 원룸" in block
    assert "warned_burnout" not in block


def test_state_block_at_top_of_dynamic() -> None:
    optimizer = SystemPromptOptimizer()
    npcs = [
        {
            "id": "kim",
            "name": "김선배",
            "role": "선배",
            "relationship_stats": {"romance": 52, "trust": 30},
        }
    ]
    player = {
        "name": "P",
        "relationships": {"kim": {"romance": 52, "trust": 30}},
        "flags": {"dating_kim": True},
    }
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player=player,
        npcs=npcs,
        memories=[],
        day=7,
    )
    state_pos = dynamic.index("## 지금 사실")
    situation_pos = dynamic.index("## 현재 상황")
    assert state_pos < situation_pos
    assert "확정: dating_kim" in dynamic
    assert "김선배: 연인" not in dynamic
    assert "로맨스(romance): 52/100" in dynamic
