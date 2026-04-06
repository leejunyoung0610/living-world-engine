# backend/src/engine/prompt_optimizer.py

from __future__ import annotations

from typing import Any


class SystemPromptOptimizer:
    """시스템 프롬프트 — 토큰 절약·static/dynamic 분리(프롬프트 캐시).

    기본 모델: Claude Sonnet 계열 한 가지 경로만 유지 (경량 모델 전용 접두 제거).
    """

    @staticmethod
    def _active_npcs_for_location(
        active_location: str, npcs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if active_location == "Unknown":
            return npcs
        active = [npc for npc in npcs if npc.get("location") == active_location]
        return active if active else npcs

    def build_system_blocks(
        self,
        world: dict[str, Any],
        player: dict[str, Any],
        active_location: str,
        npcs: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        cache_reset_flag: str | None = None,
    ) -> tuple[str, str]:
        """시스템 프롬프트를 Anthropic 프롬프트 캐시용으로 분리.

        - **static**: 턴마다 거의 동일 → 첫 system 블록에만 ``cache_control: ephemeral`` 권장.
        - **dynamic**: 장소·턴·NPC·기억 등 매 턴 변동.

        Returns:
            ``(static, dynamic)`` — 둘 다 strip 된 문자열.
        """
        active_npcs = self._active_npcs_for_location(active_location, npcs)
        npc_profiles = self._format_compact_npcs(active_npcs)
        key_memories = self._select_key_memories(memories)

        world_name = world.get("name", "알 수 없는 세계")
        world_display = world.get("name", "")
        player_name = player.get("name", "플레이어")
        turn = int(player.get("turn", 0) or 0)

        static_body = f"""너는 {world_name}의 NPC다.

**중요: 현재 세계관은 "{world_display}"입니다. 다른 세계관의 설정을 절대 사용하지 마세요.**

## 플레이어
- 이름: {player_name}
- 호칭은 반드시 "{player_name}".

## 응답 규칙
- 첫 줄: **NPC이름** (짧은 행동) 후 대사. 행동은 (괄호).
- **여러 NPC가 말할 때는 NPC마다 빈 줄 한 줄로 블록을 나눈다.** (각 블록 첫 줄은 위와 동일: 이름 (행동) 대사)
- 1~3문장 위주, 한 턴 NPC 1~3명(가능하면 1~2명). 장황한 묘사·반복 금지 — **출력 토큰 예산 내**에서 끝낸다.
- 진행 안내·플레이어님·시스템 톤 금지.
- **중요: `update_game_state` 툴을 사용하는 경우에도 반드시 같은 응답에 NPC 대사(텍스트)를 포함하세요.**
  - 툴만 보내지 마세요.
  - 대사와 툴을 항상 함께 보내세요.
  - 예외: 시스템 점검·내부 처리 등 극히 드문 경우만 텍스트 생략 가능.

## Tool (update_game_state)
**도구를 사용할 때도 NPC 대사는 반드시 같은 응답에 함께 포함하세요.**
대화에 변화가 있으면 매 턴 사용. 무의미한 한 단어("응"만 등)만 예외.
관계 변화는 상황에 맞게. new_memories importance: 1~3 일상, 4~6 의미, 7+ 중요 사건.
감정 태그: joy, sadness, anger, fear, surprise, trust, neutral
"""
        static = static_body.strip()

        prefix_lines: list[str] = []
        if turn == 0:
            prefix_lines.append("(세션 시작)")
        if cache_reset_flag:
            prefix_lines.append(f"[{cache_reset_flag}]")
        prefix = ("\n".join(prefix_lines) + "\n\n") if prefix_lines else ""

        dynamic = f"""{prefix}## 현재 상황
- 장소: {active_location}
- 턴: {turn}

## NPC
{npc_profiles if npc_profiles else "(없음)"}

## 중요 기억
{self._format_memories(key_memories)}
"""
        return static.strip(), dynamic.strip()

    def build_optimized_prompt(
        self,
        world: dict[str, Any],
        player: dict[str, Any],
        active_location: str,
        npcs: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        cache_reset_flag: str | None = None,
    ) -> str:
        """최적화된 시스템 프롬프트 (단일 문자열, 테스트·로깅용)."""
        static, dynamic = self.build_system_blocks(
            world=world,
            player=player,
            active_location=active_location,
            npcs=npcs,
            memories=memories,
            cache_reset_flag=cache_reset_flag,
        )
        parts = [p for p in (static, dynamic) if p]
        return "\n\n".join(parts)

    def _format_compact_npcs(self, npcs: list[dict[str, Any]]) -> str:
        """세계관에 관계없이 NPC 정보를 포맷팅"""
        lines: list[str] = []
        for npc in npcs:
            name = npc.get("name", "Unknown")
            role = npc.get("role", "")

            info_parts = [name]
            if role:
                info_parts.append(f"({role})")

            if "major" in npc:
                info_parts.append(f"- {npc['major']}")
            if "location" in npc:
                info_parts.append(f"위치: {npc['location']}")

            info = " ".join(info_parts)
            lines.append(info)

            details = []

            if "personality" in npc:
                details.append(f"  성격: {npc['personality']}")

            if "persona" in npc:
                persona = npc["persona"]
                if "traits" in persona:
                    traits = ", ".join(persona["traits"])
                    details.append(f"  특성: {traits}")
                if "drive" in persona:
                    details.append(f"  동기: {persona['drive']}")

            if "skills" in npc:
                skills = ", ".join(npc["skills"])
                details.append(f"  스킬: {skills}")

            if "interests" in npc:
                interests = ", ".join(npc["interests"])
                details.append(f"  관심사: {interests}")

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

            lines.append("")

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
