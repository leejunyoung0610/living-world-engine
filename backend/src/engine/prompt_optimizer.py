# backend/src/engine/prompt_optimizer.py

from __future__ import annotations

from typing import Any


class SystemPromptOptimizer:
    """시스템 프롬프트 최적화 — 필요 정보만 추려 토큰 절약"""

    def build_optimized_prompt(
        self,
        world: dict[str, Any],
        player: dict[str, Any],
        active_location: str,
        npcs: list[dict[str, Any]],
        memories: list[dict[str, Any]],
    ) -> str:
        """최적화된 시스템 프롬프트"""
        if active_location == "Unknown":
            active_npcs = npcs
        else:
            active_npcs = [
                npc for npc in npcs if npc.get("location") == active_location
            ]

        npc_profiles = self._format_compact_npcs(active_npcs)
        key_memories = self._select_key_memories(memories)

        prompt = f"""너는 {world.get("name", "알 수 없는 세계")}의 NPC다.

## 현재 상황
- 장소: {active_location}
- 턴: {player.get("turn", 0)}

## NPC
{npc_profiles if npc_profiles else "(없음)"}

## 중요 기억
{self._format_memories(key_memories)}

## 응답 규칙
- 2~3문장, 대화 중심
- 행동은 괄호 (미소), (고개 끄덕)

## Tool 사용 규칙 (중요!)
다음 경우에만 update_game_state 호출:
  ✅ 관계 변화 (호감/신뢰 증감)
  ✅ 중요한 이벤트 발생
  ✅ 의미 있는 대화/행동

다음 경우는 Tool 없이 직접 답변:
  ❌ 단순 인사 ("안녕", "잘가")
  ❌ 짧은 응답 ("응", "그래")
  ❌ 상태 변화 없는 일상 대화
  ❌ 반복적인 질문/답변

Tool을 사용하지 않으면 비용이 50% 절감되므로, 꼭 필요한 경우만 사용하라.
"""
        return prompt

    def _format_compact_npcs(self, npcs: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for npc in npcs:
            name = npc.get("name", "Unknown")
            role = npc.get("role", "")
            traits = ", ".join(
                npc.get("persona", {}).get("traits", [])[:3]
            )
            line = f"- {name} ({role}): {traits}" if role else f"- {name}: {traits}"
            lines.append(line.strip())
        return "\n".join(lines)

    def _select_key_memories(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [mem for mem in memories if mem.get("importance", 0) >= 6],
            key=lambda m: -m.get("importance", 0),
        )

    def _format_memories(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "(없음)"
        lines: list[str] = []
        for mem in memories[:5]:
            importance = mem.get("importance", 5)
            content = mem.get("content", "")
            lines.append(f"[{importance}] {content}")
        return "\n".join(lines)
