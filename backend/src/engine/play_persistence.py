"""플레이 세션 DB 스냅샷 — WorldState·대화·이벤트·장기기억 런타임 직렬화.

웹 플레이에서 **진실 공급원**은 DB `play_sessions.payload` 이다. `long_term_memory` 키가
있으면 복원 시 세션별 LTM 파일보다 우선한다(구 스냅샷 호환: 키 없으면 디스크 `_load()`만 사용).
턴 저장 시 payload에 메모리 리스트를 넣고, 동시에 `LongTermMemory._save()`로 세션 파일에도
기록되므로 파일·DB는 정상 종료 후 동기화된 상태가 된다.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .game_loop import GameEngine

PAYLOAD_VERSION = 1


def export_play_payload(engine: GameEngine) -> dict[str, Any]:
    """게임 엔진을 JSON 직렬화 가능 dict로보냄."""
    em = engine.event_manager
    mem = getattr(engine.memory, "memories", None)
    if not isinstance(mem, list):
        mem = []
    return {
        "version": PAYLOAD_VERSION,
        "world_state": engine.state.to_save_dict(),
        "conversation_history": deepcopy(engine.conversation_history),
        "events": {
            "triggered_events": deepcopy(em.triggered_events),
            "cooldowns": dict(em.cooldowns),
        },
        "long_term_memory": {"memories": deepcopy(mem)},
    }


def apply_play_payload(engine: GameEngine, payload: dict[str, Any] | None) -> None:
    """스냅샷을 엔진에 적용. `initialize_from_dicts` 직후 호출."""
    if not payload:
        return
    ws = payload.get("world_state")
    if isinstance(ws, dict) and ws:
        engine.state.restore_from_save_dict(ws)
    ch = payload.get("conversation_history")
    if isinstance(ch, list):
        engine.conversation_history = deepcopy(ch)
    ev = payload.get("events") or {}
    if isinstance(ev, dict):
        te = ev.get("triggered_events")
        if isinstance(te, list):
            engine.event_manager.triggered_events = deepcopy(te)
        cd = ev.get("cooldowns")
        if isinstance(cd, dict):
            engine.event_manager.cooldowns = {str(k): int(v) for k, v in cd.items()}
    ltm = payload.get("long_term_memory")
    if isinstance(ltm, dict):
        mems = ltm.get("memories")
        if isinstance(mems, list):
            engine.memory.memories = deepcopy(mems)
            save = getattr(engine.memory, "_save", None)
            if callable(save):
                save()


def sync_engine_after_restore(engine: GameEngine) -> None:
    """복원 후 검증기·NPC 이름·기억 검색용 이름 동기화."""
    engine.validator.set_valid_characters(engine.state.get_all_character_names())
    npc_names = [n.get("name") for n in engine.state.npcs if n.get("name")]
    engine.context_manager.set_npc_names(npc_names)
    engine.memory.set_npc_names(npc_names)
