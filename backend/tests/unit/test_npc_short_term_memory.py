"""NPC 단기기억."""

from backend.src.engine.npc_short_term_memory import NpcShortTermMemory


def test_add_and_format() -> None:
    stm = NpcShortTermMemory()
    stm.add_entry("npc1", turn=3, summary="플레이어가 약속을 지켰다")
    block = stm.format_for_prompt(
        [{"id": "npc1", "name": "아현"}],
        current_turn=5,
    )
    assert "아현" in block
    assert "약속" in block


def test_prune_expired() -> None:
    stm = NpcShortTermMemory()
    stm.add_entry("npc1", turn=1, summary="오래된 기억", ttl_turns=2)
    stm.prune(current_turn=5)
    block = stm.format_for_prompt([{"id": "npc1", "name": "A"}], current_turn=5)
    assert "오래된" not in block


def test_apply_updates_resolves_character() -> None:
    stm = NpcShortTermMemory()

    def resolve(name: str) -> str | None:
        return "id_x" if name == "엘레나" else None

    applied = stm.apply_updates(
        [{"character": "엘레나", "summary": "진심 어린 대화를 나눴다"}],
        resolve_npc_id=resolve,
        turn=4,
    )
    assert len(applied) == 1
    assert "id_x" in stm.by_npc
