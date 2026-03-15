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
        cache_reset_flag: str | None = None,
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
        
        # Turn 정보를 포함하여 캐시 무효화 (Turn 0일 때만 새로운 게임 세션)
        turn = player.get("turn", 0)
        session_note = f" (세션 시작)" if turn == 0 else ""
        
        # Cache 강제 초기화 플래그 (--force-cache-reset 옵션)
        cache_note = f" [{cache_reset_flag}]" if cache_reset_flag else ""

        prompt = f"""너는 {world.get("name", "알 수 없는 세계")}의 NPC다.{session_note}{cache_note}

**중요: 현재 세계관은 "{world.get("name", "")}"입니다. 다른 세계관의 설정을 절대 사용하지 마세요.**

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
- 대화 NPC는 한 턴당 플레이어 제외 최대 3명, 평균 1~2명 대화

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
        """세계관에 관계없이 NPC 정보를 포맷팅"""
        lines: list[str] = []
        for npc in npcs:
            name = npc.get("name", "Unknown")
            role = npc.get("role", "")
            
            # 기본 정보
            info_parts = [name]
            if role:
                info_parts.append(f"({role})")
            
            # 세계관별 핵심 정보 추가
            # 1. 학과 (campus)
            if "major" in npc:
                info_parts.append(f"- {npc['major']}")
            
            # 2. 위치 (arcane_academy)
            if "location" in npc:
                info_parts.append(f"위치: {npc['location']}")
            
            info = " ".join(info_parts)
            lines.append(info)
            
            # 상세 정보
            details = []
            
            # 3. 성격 (campus)
            if "personality" in npc:
                details.append(f"  성격: {npc['personality']}")
            
            # 4. Persona (arcane_academy)
            if "persona" in npc:
                persona = npc["persona"]
                if "traits" in persona:
                    traits = ", ".join(persona["traits"])
                    details.append(f"  특성: {traits}")
                if "drive" in persona:
                    details.append(f"  동기: {persona['drive']}")
            
            # 5. 스킬 (arcane_academy)
            if "skills" in npc:
                skills = ", ".join(npc["skills"])
                details.append(f"  스킬: {skills}")
            
            # 6. 관심사 (campus)
            if "interests" in npc:
                interests = ", ".join(npc["interests"])
                details.append(f"  관심사: {interests}")
            
            # 7. 말투 (공통, 간단히)
            if "speaking_style" in npc:
                style = npc["speaking_style"]
                if isinstance(style, str):
                    details.append(f"  말투: {style}")
                elif isinstance(style, dict):
                    formality = style.get("formality", "")
                    mood = style.get("default_mood", "")
                    if formality or mood:
                        details.append(f"  말투: {formality}, {mood}")
            
            if details:
                lines.extend(details)
            
            lines.append("")  # 빈 줄 추가
        
        return "\n".join(lines).strip()

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
