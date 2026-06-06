"""플레이 세션 DB 스냅샷 — WorldState·대화·이벤트·장기기억 런타임 직렬화.

웹 플레이에서 **진실 공급원**은 DB `play_sessions.payload` 이다. `long_term_memory` 키가
있으면 복원 시 세션별 LTM 파일보다 우선한다(구 스냅샷 호환: 키 없으면 디스크 `_load()`만 사용).
턴 저장 시 payload에 메모리 리스트를 넣고, 동시에 `LongTermMemory._save()`로 세션 파일에도
기록되므로 파일·DB는 정상 종료 후 동기화된 상태가 된다.

`regenerate_checkpoint`(payload 최상위): 직전 턴 직전 엔진 스냅샷 — ``ダ시``(재생성) 시 복원.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PAYLOAD_VERSION = 1


def strip_nested_regenerate_checkpoint(blob: dict[str, Any]) -> dict[str, Any]:
    """순환·팽창 방지 — 체크포인트 dict 에서 ``regenerate_checkpoint`` 키만 제거."""
    out = deepcopy(blob)
    out.pop("regenerate_checkpoint", None)
    return out


def export_play_payload(engine: Any) -> dict[str, Any]:
    """게임 엔진을 JSON 직렬화 가능 dict로보냄."""
    em = engine.event_manager
    mem = getattr(engine.memory, "memories", None)
    if not isinstance(mem, list):
        mem = []
    out: dict[str, Any] = {
        "version": PAYLOAD_VERSION,
        "world_state": engine.state.to_save_dict(),
        "conversation_history": deepcopy(engine.conversation_history),
        "events": {
            "triggered_events": deepcopy(em.triggered_events),
            "cooldowns": dict(em.cooldowns),
        },
        "pending_event_hints": deepcopy(getattr(engine, "pending_event_hints", [])),
        "long_term_memory": {"memories": deepcopy(mem)},
    }

    ut = getattr(engine, "usage_tracker", None)
    if ut is not None:
        out["usage_tracker"] = {
            "total_calls": int(getattr(ut, "total_calls", 0)),
            "total_input_tokens": int(getattr(ut, "total_input_tokens", 0)),
            "total_output_tokens": int(getattr(ut, "total_output_tokens", 0)),
            "total_cache_creation": int(getattr(ut, "total_cache_creation", 0)),
            "total_cache_read": int(getattr(ut, "total_cache_read", 0)),
            "total_cost": float(getattr(ut, "total_cost", 0.0)),
            "turn_costs": deepcopy(getattr(ut, "turn_costs", [])),
        }

    return out


def apply_play_payload(engine: Any, payload: dict[str, Any] | None) -> None:
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
    peh = payload.get("pending_event_hints")
    if isinstance(peh, list):
        engine.pending_event_hints = deepcopy(peh)
    ltm = payload.get("long_term_memory")
    if isinstance(ltm, dict):
        mems = ltm.get("memories")
        if isinstance(mems, list):
            engine.memory.memories = deepcopy(mems)
            save = getattr(engine.memory, "_save", None)
            if callable(save):
                save()

    ut_raw = payload.get("usage_tracker")
    if isinstance(ut_raw, dict):
        ut = getattr(engine, "usage_tracker", None)
        if ut is not None:
            ut.total_calls = int(ut_raw.get("total_calls", 0))
            ut.total_input_tokens = int(ut_raw.get("total_input_tokens", 0))
            ut.total_output_tokens = int(ut_raw.get("total_output_tokens", 0))
            ut.total_cache_creation = int(ut_raw.get("total_cache_creation", 0))
            ut.total_cache_read = int(ut_raw.get("total_cache_read", 0))
            ut.total_cost = float(ut_raw.get("total_cost", 0.0))
            tc = ut_raw.get("turn_costs")
            ut.turn_costs = deepcopy(tc) if isinstance(tc, list) else []


def sync_engine_after_restore(engine: Any) -> None:
    """복원 후 검증기·NPC 이름·기억 검색용 이름 동기화."""
    engine.validator.set_valid_characters(engine.state.get_all_character_names())
    npc_names = [n.get("name") for n in engine.state.npcs if n.get("name")]
    engine.context_manager.set_npc_names(npc_names)
    engine.memory.set_npc_names(npc_names)
