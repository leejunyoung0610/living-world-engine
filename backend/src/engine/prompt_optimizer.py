# backend/src/engine/prompt_optimizer.py

from __future__ import annotations

from typing import Any


class SystemPromptOptimizer:
    """시스템 프롬프트 최적화 — 필요 정보만 추려 토큰 절약

    모델 스위칭: **공통 프롬프트(슬림)** + Haiku 등 경량 모델에만 **추가 지침** 접두.
    Sonnet은 공통만 사용해 토큰·과잉 설명을 줄인다.
    """

    # Sonnet에는 넣지 않음. llm_model 에 "haiku" 가 있을 때만 앞에 붙는다.
    HAIKU_SUPPLEMENT = """
## [Haiku·경량 모델 전용 추가 지침]
아래는 공통 지시를 지키기 어려울 때만 보강하는 규칙이다. 세계관·역할은 공통 프롬프트와 동일.

⚠️ 위반 금지:
1) **NPC만 연기한다.** 진행 안내·고객지원·메타 해설이 아니다.
   - 금지: "플레이어님", "플레이어", "사용자님", "스토리를 진행", "현재 상황:" 목록 후 사용자에게 지시
   - 금지 문패: "질문이 명확하지 않습니다", "죄송하지만 맥락이", "명확히 알려주세요", "다음 행동을 정해주시면"

2) 플레이어 호칭은 공통의 "## 플레이어" 이름만 사용한다.

3) **애매한 한 마디**는 직전 맥락으로 추론해 NPC로 반응. 여러 갈래면 짧게 되물음 (예: "어, 누구 말이야? 방금 헤어진 이준호?"). 메타로 되묻지 말 것.

4) 예시:
   🚫 "플레이어님, 질문이 명확하지 않습니다…"
   ✅ "**이준호** (뒤돌아보며) 어, 나? 도서관 가는 중인데, 왜?"

5) **update_game_state**: 관계·감정이 조금이라도 바뀌면 가급적 매 턴 호출. 중요 전환은 new_memories importance 7+. "응" 한 마디만이면 생략 가능. 툴을 쓸 때도 **같은 응답에 NPC 대사 텍스트를 반드시 함께** 출력한다.
"""

    @staticmethod
    def _is_haiku_model(llm_model: str | None) -> bool:
        if not llm_model:
            return False
        return "haiku" in llm_model.lower()

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
        llm_model: str | None = None,
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
- 1~3문장 위주, 한 턴 NPC 1~3명.
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
        static_body = static_body.strip()
        if self._is_haiku_model(llm_model):
            static = (
                f"{self.HAIKU_SUPPLEMENT.strip()}\n\n---\n\n{static_body}"
            ).strip()
        else:
            static = static_body

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
        llm_model: str | None = None,
    ) -> str:
        """최적화된 시스템 프롬프트 (단일 문자열, 테스트·로깅용).

        Args:
            llm_model: 설정된 API 모델 ID. 이름에 'haiku' 포함 시 HAIKU_SUPPLEMENT 접두.
        """
        static, dynamic = self.build_system_blocks(
            world=world,
            player=player,
            active_location=active_location,
            npcs=npcs,
            memories=memories,
            cache_reset_flag=cache_reset_flag,
            llm_model=llm_model,
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
