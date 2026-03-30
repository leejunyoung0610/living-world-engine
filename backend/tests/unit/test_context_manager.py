import pytest

from backend.src.engine.context_manager import ContextManager


@pytest.fixture
def context_manager():
    cm = ContextManager()
    cm.set_npc_names(["루아", "엘레나"])
    return cm


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


def test_token_counting(context_manager):
    messages = [{"content": "a" * 400}, {"content": "b" * 400}]
    tokens = context_manager._count_tokens(messages)
    assert 180 <= tokens <= 220


def test_empty_history(context_manager):
    optimized = context_manager.build_context("test", [], max_tokens=3000)
    assert optimized == []


def test_budget_trims_layer2_then_fits(context_manager):
    """예산 초과 시 Layer2 턴 수·필요 시 Layer1을 줄인다."""
    history = []
    for i in range(25):
        history.append({"role": "user", "content": f"Turn {i} 루아에게 말함"})
        history.append({"role": "assistant", "content": "x" * 300})
    optimized = context_manager.build_context("루아", history, max_tokens=400)
    assert len(optimized) < len(history)
    assert optimized[-1] == history[-1]


def test_layer2_empty_when_no_sampling_window(context_manager):
    """히스토리가 짧으면 Layer1만으로 구성"""
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    optimized = context_manager.build_context("test", history, max_tokens=3000)
    assert optimized == history
