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
        # location 필드가 없으면 모든 NPC 포함
        if active_location == "Unknown":
            active_npcs = npcs
        else:
            active_npcs = [
                npc for npc in npcs if npc.get("location") == active_location
            ]
            # location이 있는데 필터링 결과가 비어있으면 모든 NPC 포함
            if not active_npcs:
                active_npcs = npcs

        npc_profiles = self._format_compact_npcs(active_npcs)
        key_memories = self._select_key_memories(memories)
        
        player_name = player.get("name", "플레이어")

        prompt = f"""너는 {world.get("name", "알 수 없는 세계")}의 NPC다.

**중요: 현재 세계관은 "{world.get("name", "")}"입니다. 다른 세계관(마법학교, 판타지 등)의 설정을 절대 사용하지 마세요.**

## 플레이어
- 이름: {player_name}
- 플레이어를 부를 때 반드시 "{player_name}"로 호칭하세요.

## 현재 상황
- 장소: {active_location}
- 턴: {player.get("turn", 0)}

## NPC
{npc_profiles if npc_profiles else "(없음)"}

## 중요 기억
{self._format_memories(key_memories)}

## 응답 규칙
- [반드시 첫 줄에 말하는 NPC 이름을 명시하세요]: "[NPC이름] : (행동)" 같은줄 출력
- 예시: "**김서연** (미소를 지으며)" 또는 "**이준호** (고개를 끄덕이며)"
- 1~2문장, 대화 중심
- 행동은 괄호로 표시: (미소), (고개 끄덕)
- 대화 NPC는 한 턴당 최대 3명 평균 1~2명 대화

## Tool 사용 규칙
**기본적으로 update_game_state를 사용하세요.**

Tool을 사용하지 않는 경우 (매우 제한적):
  ❌ "안녕"만 하는 경우
  ❌ "응", "그래" 같은 1단어 응답

대부분의 대화는 Tool을 사용해 관계 변화를 기록하세요:
  ✅ 새로운 정보 교환 → trust +1
  ✅ 친근한 대화 → affection +1
  ✅ 의미 있는 대화 → 적절한 stat 증가
"""
        return prompt

    def _format_compact_npcs(self, npcs: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for npc in npcs:
            name = npc.get("name", "Unknown")
            role = npc.get("role", "")
            major = npc.get("major", "")
            personality = npc.get("personality", "")
            
            # 기본 정보
            if major:
                info = f"- {name} ({role}, {major})"
            else:
                info = f"- {name} ({role})" if role else f"- {name}"
            
            # 성격 추가
            if personality:
                info += f"\n  성격: {personality}"
            
            lines.append(info)
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
