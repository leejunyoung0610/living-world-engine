"""play_persistence — DB 스냅샷에 장기기억 포함·복원."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.src.engine.play_persistence import apply_play_payload, export_play_payload


def test_export_import_long_term_memory() -> None:
    mem = [{"id": "a1", "content": "saved", "player_id": "default", "importance": 8, "tags": []}]
    engine = MagicMock()
    engine.state.to_save_dict.return_value = {"turn": 1, "day": 1}
    engine.conversation_history = [{"role": "user", "content": "hi"}]
    em = MagicMock()
    em.triggered_events = []
    em.cooldowns = {}
    engine.event_manager = em
    engine.memory = MagicMock(memories=list(mem), _save=MagicMock())

    payload = export_play_payload(engine)
    assert payload["long_term_memory"]["memories"] == mem

    engine2 = MagicMock()
    engine2.state = MagicMock()
    engine2.conversation_history = []
    engine2.event_manager = MagicMock(triggered_events=[], cooldowns={})
    engine2.memory = MagicMock(memories=[], _save=MagicMock())

    apply_play_payload(engine2, payload)
    assert engine2.memory.memories == mem
    engine2.memory._save.assert_called_once()
