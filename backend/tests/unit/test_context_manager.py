import pytest

from backend.src.engine.context_manager import ContextManager


@pytest.fixture
def context_manager():
    return ContextManager()


@pytest.fixture
def sample_history():
    history = []
    for i in range(20):
        history.append({"role": "user", "content": f"Turn {i+1} user input"})
        history.append({"role": "assistant", "content": f"Turn {i+1} assistant response"})
    return history


def test_keep_recent(context_manager, sample_history):
    recent = context_manager._keep_recent(sample_history, 10)
    assert len(recent) == 20
    assert "Turn 20" in recent[-1]["content"]


def test_build_context_recent_only(context_manager):
    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"Turn {i+1}"})
        history.append({"role": "assistant", "content": "Response"})

    optimized = context_manager.build_context("test", history, max_tokens=3000)
    assert len(optimized) == len(history)


def test_build_context_with_sampling(context_manager):
    history = []
    for i in range(20):
        history.append({"role": "user", "content": "a" * 200})
        history.append({"role": "assistant", "content": "b" * 200})

    optimized = context_manager.build_context("루아", history, max_tokens=500)
    assert len(optimized) < len(history)
    assert optimized[-1] == history[-1]


def test_importance_calculation(context_manager):
    msg_with_tool = {
        "content": [
            {"type": "text", "text": "response"},
            {"type": "tool_use", "name": "update_game_state"},
        ]
    }
    score1 = context_manager._calculate_importance(msg_with_tool, "test")
    assert score1 >= 5.0

    msg_with_npc = {"content": "루아와 대화했다"}
    score2 = context_manager._calculate_importance(msg_with_npc, "루아 기억나?")
    assert score2 >= 2.0

    msg_normal = {"content": "test"}
    score3 = context_manager._calculate_importance(msg_normal, "other")
    assert score3 >= 0.0


def test_token_counting(context_manager):
    messages = [{"content": "a" * 400}, {"content": "b" * 400}]
    tokens = context_manager._count_tokens(messages)
    assert 180 <= tokens <= 220


def test_empty_history(context_manager):
    optimized = context_manager.build_context("test", [], max_tokens=3000)
    assert optimized == []


def test_sample_important_with_budget(context_manager):
    old_messages = [
        {"content": "a" * 400},
        {"content": "b" * 400},
        {"content": "c" * 400},
    ]
    selected = context_manager._sample_important(old_messages, "test", token_budget=150)
    assert 1 <= len(selected) <= 2
