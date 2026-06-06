"""
EventManager - 이벤트 시스템

설계 원칙
~~~~~~~~~

- **이벤트 = 자원 스탯 / 플래그 / 내러티브 힌트**. ``hp``·``stress``·``focus`` 같은
  플레이어 자원 수치를 가끔(조건/확률) 변동시키는 게 주 용도.
- **감정·관계 (affection·trust·respect·fear·loyalty·romance·disgust·wrath) 는 LLM 이 이야기 흐름에서
  자연스럽게** ``update_relationship`` 으로 변동. 이벤트 *효과* 로는 만지지 않는다.
  (조건은 ``relationship_threshold`` 로 *읽는* 건 허용 — 트리거에는 유용.)

조건 타입
~~~~~~~~~

- ``turn_range`` (기존): 턴 구간
- ``variable_threshold`` (기존): ``world.world_variables[key]`` 비교
- ``relationship_threshold`` (기존): ``player.relationships.*[stat]`` 비교.
  선택적 ``npc_id`` 가 있으면 해당 NPC만, 없으면 1명이라도 충족 시 True (하위 호환).
- ``resource_stat_threshold`` (신규): ``player.stats[key]`` 비교
- ``flag`` (신규): ``player.flags[key] == equals``
- ``time_window`` (신규): ``min_day``/``max_day``/``phase``("day"/"night")
- ``compound`` (신규): ``op="and"|"or"`` + ``conditions[]`` (재귀 가능)

효과 타입 (PR-1)
~~~~~~~~~~~~~~~~

- ``resource_stat``: ``player.stats[key]`` 가감 + ``world.stats_schema.resource[key]`` clamp
- ``flag_set``: ``player.flags[key]`` 설정/해제
- ``narrative``: state 변경 없이 LLM 응답 합성 시 힌트로만 사용

(``relationship`` / ``world_variable`` 효과는 PR-2 에서 결정.)
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import WorldState

OPERATORS: dict[str, Any] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

# 같은 턴에 발동할 수 있는 이벤트 최대 개수 (월드별 ``world_variables.max_events_per_turn`` 으로 덮어쓸 수 있음)
DEFAULT_MAX_EVENTS_PER_TURN = 1


class EventManager:
    """조건 기반 이벤트 관리"""

    def __init__(self) -> None:
        self.event_templates: list[dict[str, Any]] = []
        self.triggered_events: list[dict[str, Any]] = []
        self.cooldowns: dict[str, int] = {}  # event_id → 남은 쿨다운 턴

    # ── 로딩 ──

    def load_events(self, events_data: list[dict[str, Any]]) -> None:
        """이벤트 템플릿을 리스트 데이터로 로드"""
        self.event_templates = events_data

    def load_events_from_file(self, filepath: str | Path) -> None:
        """events.json 파일에서 이벤트 로드

        Raises:
            FileNotFoundError: 파일 없음
            json.JSONDecodeError: JSON 파싱 실패
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"이벤트 파일을 찾을 수 없습니다: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "events" in data:
            self.event_templates = data["events"]
        elif isinstance(data, list):
            self.event_templates = data
        else:
            self.event_templates = []

    # ── 조건 체크 ──

    def check_events(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """현재 상태에서 트리거 가능한 이벤트 목록 반환.

        - ``priority`` 큰 순으로 정렬 (없으면 0).
        - 쿨다운 중인 이벤트는 제외.
        - 같은 턴 발동 캡(``max_events_per_turn``) 적용은 호출자 책임 (game_loop).

        Args:
            state: ``WorldState.snapshot()`` 결과.
        """
        triggered: list[dict[str, Any]] = []

        for event in self.event_templates:
            event_id = event.get("id", "")
            if event_id in self.cooldowns:
                continue
            if event.get("once") and event_id:
                if any(rec.get("id") == event_id for rec in self.triggered_events):
                    continue

            condition = event.get("condition", {})
            if self._evaluate_condition(condition, state):
                triggered.append(event)

        triggered.sort(key=lambda e: int(e.get("priority", 0) or 0), reverse=True)
        return triggered

    def _evaluate_condition(self, condition: dict[str, Any], state: dict[str, Any]) -> bool:
        """단일 조건 평가. 알 수 없는 타입은 False (안전 디폴트)."""
        if not isinstance(condition, dict):
            return False
        cond_type = condition.get("type", "")

        if cond_type == "turn_range":
            turn = state.get("turn", 0)
            return condition.get("min_turn", 0) <= turn < condition.get("max_turn", 999)

        if cond_type == "variable_threshold":
            variable = condition.get("variable", "")
            world_vars = state.get("world", {}).get("world_variables", {}) or {}
            actual = world_vars.get(variable, 0)
            return self._compare(actual, condition.get("op", ">="), condition.get("value", 0))

        if cond_type == "relationship_threshold":
            return self._evaluate_relationship_threshold(condition, state)

        if cond_type == "resource_stat_threshold":
            stat = condition.get("stat", "")
            op_str = condition.get("op", ">=")
            threshold = condition.get("value", 0)
            stats = state.get("player", {}).get("stats", {}) or {}
            return self._compare(stats.get(stat, 0), op_str, threshold)

        if cond_type == "flag":
            key = condition.get("key", "")
            flags = state.get("player", {}).get("flags", {}) or {}
            actual = flags.get(key)
            if "equals" in condition:
                return actual == condition["equals"]
            # ``equals`` 가 비어있으면 단순 truthy 검사 — UGC 작성자의 짧은 표현 허용
            return bool(actual)

        if cond_type == "time_window":
            day = int(state.get("day", 1) or 1)
            if "min_day" in condition and day < int(condition["min_day"]):
                return False
            if "max_day" in condition and day > int(condition["max_day"]):
                return False
            if "phase" in condition:
                # phase 는 명시적 state["phase"] 가 우선. 없으면 짝수 turn=day, 홀수=night.
                actual_phase = state.get("phase")
                if actual_phase is None:
                    actual_phase = "day" if (int(state.get("turn", 0) or 0) % 2 == 0) else "night"
                if actual_phase != condition["phase"]:
                    return False
            return True

        if cond_type == "compound":
            op = str(condition.get("op", "and")).lower()
            conditions = condition.get("conditions", [])
            if not isinstance(conditions, list):
                return False
            if op == "or":
                return any(self._evaluate_condition(c, state) for c in conditions)
            return all(self._evaluate_condition(c, state) for c in conditions)

        return False

    def _evaluate_relationship_threshold(
        self, condition: dict[str, Any], state: dict[str, Any]
    ) -> bool:
        """관계 스탯 임계값. ``npc_id`` 가 있으면 해당 NPC만, 없으면 아무 NPC 충족 시 True."""
        stat = condition.get("stat", "")
        op_str = condition.get("op", ">=")
        threshold = condition.get("value", 0)
        relationships = state.get("player", {}).get("relationships", {}) or {}
        npc_id = condition.get("npc_id")
        if npc_id:
            npc_rels = relationships.get(npc_id)
            if not isinstance(npc_rels, dict):
                return False
            return self._compare(npc_rels.get(stat, 0), op_str, threshold)
        for _npc_id, stats in relationships.items():
            if not isinstance(stats, dict):
                continue
            if self._compare(stats.get(stat, 0), op_str, threshold):
                return True
        return False

    @staticmethod
    def _compare(actual: Any, op_str: str, threshold: Any) -> bool:
        """연산자 문자열로 비교"""
        op_func = OPERATORS.get(op_str)
        if op_func is None:
            return False
        return op_func(actual, threshold)

    # ── 효과 적용 ──

    @staticmethod
    def _resolve_resource_clamp(world_data: dict[str, Any], key: str) -> tuple[int, int] | None:
        """``world.stats_schema.resource[key].{min,max}`` 가 있으면 그 범위.

        구버전 ``standard_stats`` 는 *관계 스탯* 정의이므로 자원 스탯 clamp 에는 사용하지 않는다.
        """
        schema = world_data.get("stats_schema") if isinstance(world_data, dict) else None
        if not isinstance(schema, dict):
            return None
        resource = schema.get("resource")
        if not isinstance(resource, dict):
            return None
        cfg = resource.get(key)
        if not isinstance(cfg, dict):
            return None
        if "min" in cfg and "max" in cfg:
            try:
                return int(cfg["min"]), int(cfg["max"])
            except (TypeError, ValueError):
                return None
        return None

    def apply_effects(
        self,
        state_obj: WorldState,
        effects: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """이벤트의 ``effects`` 배열을 ``WorldState`` 에 적용.

        지원 효과 (PR-1):
            - ``resource_stat`` (구 ``player_stat`` 도 별칭 허용): ``key``, ``change``
            - ``flag_set``: ``key``, ``value``
            - ``narrative``: ``text`` (state 변경 없음, 응답 합성용 힌트)

        다른 타입(``relationship``/``world_variable`` 등)은 PR-1 에서 의도적으로 미지원.
        UGC 측 오타 방지를 위해 알 수 없는 타입도 조용히 무시한다.

        Returns:
            적용 내역 리스트. 각 항목 형태 예::

                {"type": "resource_stat", "key": "stress", "change": -2, "before": 7, "after": 5}
                {"type": "flag_set", "key": "warned_burnout", "before": None, "after": True}
                {"type": "narrative", "text": "..."}
        """
        applied: list[dict[str, Any]] = []
        if not isinstance(effects, list):
            return applied

        for eff in effects:
            if not isinstance(eff, dict):
                continue
            eff_type = eff.get("type", "")

            if eff_type in ("resource_stat", "player_stat"):
                key = str(eff.get("key", "")).strip()
                if not key:
                    continue
                try:
                    change = int(eff.get("change", 0))
                except (TypeError, ValueError):
                    continue
                clamp = self._resolve_resource_clamp(state_obj.world, key)
                before, after = state_obj.update_player_stat(key, change, clamp=clamp)
                applied.append(
                    {
                        "type": "resource_stat",
                        "key": key,
                        "change": change,
                        "before": before,
                        "after": after,
                    }
                )

            elif eff_type == "flag_set":
                key = str(eff.get("key", "")).strip()
                if not key:
                    continue
                value = eff.get("value")
                before, after = state_obj.set_flag(key, value)
                applied.append(
                    {"type": "flag_set", "key": key, "before": before, "after": after}
                )

            elif eff_type == "narrative":
                text = str(eff.get("text", ""))
                if text:
                    applied.append({"type": "narrative", "text": text})

            # 그 외 타입은 PR-1 에서 무시 (PR-2 에서 relationship / world_variable 검토)

        return applied

    # ── 이벤트 발동 ──

    def trigger_event(self, event_id: str) -> dict[str, Any] | None:
        """이벤트 발동: 쿨다운 설정 + 히스토리 기록

        Returns:
            발동된 이벤트 dict, 없으면 None
        """
        event = self._get_event(event_id)
        if event is None:
            return None

        self.cooldowns[event_id] = event.get("cooldown", 10)
        self.triggered_events.append({"id": event_id, "event": event})
        return event

    def _get_event(self, event_id: str) -> dict[str, Any] | None:
        """ID로 이벤트 템플릿 조회"""
        for event in self.event_templates:
            if event.get("id") == event_id:
                return event
        return None

    # ── 쿨다운 ──

    def tick_cooldowns(self) -> None:
        """쿨다운 1턴 감소, 0 이하면 제거"""
        expired = []
        for event_id, remaining in self.cooldowns.items():
            self.cooldowns[event_id] = remaining - 1
            if remaining - 1 <= 0:
                expired.append(event_id)

        for event_id in expired:
            del self.cooldowns[event_id]
