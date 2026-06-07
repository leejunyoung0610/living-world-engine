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
    """Layer1(최근 5턴)만 — Layer2 비활성 시 짧은 히스토리는 전부 유지."""
    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"Turn {i+1}"})
        history.append({"role": "assistant", "content": "Response"})

    optimized = context_manager.build_context("test", history, max_tokens=3000)
    assert optimized == history


def test_build_context_keeps_last_seven_turns(context_manager):
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"Turn {i+1}"})
        history.append({"role": "assistant", "content": "Response"})

    optimized = context_manager.build_context("test", history, max_tokens=3000)
    assert len(optimized) == 14
    assert optimized[0]["content"] == "Turn 4"
    assert optimized[-1] == history[-1]


def test_build_context_preserves_user_message_without_npc_name(context_manager):
    """NPC 이름 없는 유저 발언도 최근 5턴 안이면 LLM 컨텍스트에 포함."""
    history = []
    for i in range(6):
        history.append({"role": "user", "content": f"Turn {i+1}"})
        history.append({"role": "assistant", "content": "**루아** (웃으며) 응"})
    history[8] = {"role": "user", "content": "나 내일 일 뺐어 반장님한테 얘기해서"}
    history[10] = {"role": "user", "content": "여기 침대에서 자 난 소파에서 잘게"}
    history[11] = {"role": "assistant", "content": "**루아** 일요일 노가다 없어?"}

    optimized = context_manager.build_context("test", history, max_tokens=3000)
    joined = " ".join(m["content"] for m in optimized)
    assert "일 뺐어" in joined
    assert optimized[-1] == history[-1]


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
    # 한글 보정: chars / 1.2
    assert int(800 / 1.2) - 2 <= tokens <= int(800 / 1.2) + 2


def test_empty_history(context_manager):
    optimized = context_manager.build_context("test", [], max_tokens=3000)
    assert optimized == []


def test_budget_trims_layer1_when_over_budget(context_manager):
    """예산 초과 시 Layer1 턴 수만 축소 (Layer2 기본 비활성)."""
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


def test_max_stored_turns_constant():
    assert ContextManager.MAX_STORED_TURNS == 30
    assert ContextManager.KEEP_RECENT_TURNS == 7
    assert ContextManager.NPC_RECENT_TURNS == 0
