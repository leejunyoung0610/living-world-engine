# backend/src/engine/prompt_optimizer.py

from __future__ import annotations

import re
from typing import Any

from .relationship_stats import (
    RELATIONSHIP_STAT_LABELS_KO,
    RELATIONSHIP_STAT_ORDER,
    build_session_relationship_view,
)


class SystemPromptOptimizer:
    """시스템 프롬프트 — 토큰 절약·static/dynamic 분리(프롬프트 캐시).

    기본 모델: Claude Sonnet 계열 한 가지 경로만 유지 (경량 모델 전용 접두 제거).
    """

    @staticmethod
    def _dialogue_npc_cap(world: dict[str, Any]) -> int:
        """매 턴 시스템 프롬프트에 넣을 NPC 프로필 상한(장소 무관).

        월드 ``world_variables.dialogue_npc_cap`` (선택). 기본 4, 허용 2–12.
        """
        vars_ = world.get("world_variables")
        raw = vars_.get("dialogue_npc_cap", 4) if isinstance(vars_, dict) else 4
        try:
            c = int(raw)
        except (TypeError, ValueError):
            c = 4
        return max(2, min(12, c))

    @staticmethod
    def _parse_assistant_speaker_names(assistant_text: str) -> list[str]:
        """플레이 응답 규칙(블록별 첫 줄: 이름 (행동) …)에서 화자 이름 후보 추출."""
        names: list[str] = []
        if not assistant_text or not assistant_text.strip():
            return names
        for block in re.split(r"\n\s*\n+", assistant_text.strip()):
            line = block.strip().split("\n", 1)[0].strip()
            line = line.replace("**", "").strip()
            if not line:
                continue
            if "(" in line:
                name_candidate = line.split("(", 1)[0].strip()
            else:
                parts = line.split()
                name_candidate = parts[0].strip() if parts else ""
            if name_candidate and name_candidate not in names:
                names.append(name_candidate)
        return names

    @staticmethod
    def _select_npcs_for_dialogue(
        user_message: str,
        npcs: list[dict[str, Any]],
        recent_conversation: list[dict[str, Any]],
        *,
        cap: int,
    ) -> list[dict[str, Any]]:
        """장소 불문 — 사용자 지목·직전 발화 화자·안정 순서로 참가 NPC 선택."""
        if not npcs:
            return []
        cap = max(1, min(cap, len(npcs)))
        if len(npcs) <= cap:
            return list(npcs)

        um = user_message or ""
        selected: list[dict[str, Any]] = []
        seen: set[Any] = set()

        def add_npc(n: dict[str, Any]) -> None:
            nid = n.get("id")
            if nid in seen:
                return
            seen.add(nid)
            selected.append(n)

        # 1) 플레이어 메시지에 이름이 문자열 포함된 NPC
        for n in npcs:
            name = str(n.get("name", "")).strip()
            if name and name in um:
                add_npc(n)
            if len(selected) >= cap:
                return selected[:cap]

        # 2) 직전 assistant 발화 순(최근 → 과거)에서 화자 매칭
        for msg in reversed(recent_conversation):
            if msg.get("role") != "assistant":
                continue
            content = str(msg.get("content", ""))
            for sp in SystemPromptOptimizer._parse_assistant_speaker_names(content):
                for n in npcs:
                    if str(n.get("name", "")).strip() == sp:
                        add_npc(n)
                        break
                if len(selected) >= cap:
                    return selected[:cap]

        # 3) 남은 칸은 ``npcs`` 정의 순으로 채움
        for n in npcs:
            add_npc(n)
            if len(selected) >= cap:
                break
        return selected[:cap]

    @staticmethod
    def _world_lore_paragraphs(world: dict[str, Any]) -> tuple[str, str]:
        """(한 줄 요약, 상세 세계관) — `description` / `world_setting`·레거시 `setting`."""
        desc = world.get("description")
        d = desc.strip() if isinstance(desc, str) else ""

        raw = world.get("world_setting")
        chunks: list[str] = []
        if isinstance(raw, str) and raw.strip():
            chunks.append(raw.strip())
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    chunks.append(item.strip())
        if not chunks:
            leg = world.get("setting")
            if isinstance(leg, str) and leg.strip():
                chunks.append(leg.strip())
        lore = "\n\n".join(chunks) if chunks else ""
        return d, lore

    @staticmethod
    def _format_player_stats_block(player: dict[str, Any]) -> str:
        stats = player.get("stats")
        if not isinstance(stats, dict) or not stats:
            return (
                "(없음 — `characters.json` 의 `player.stats` 에 숫자 키를 원하는 만큼 정의하세요. "
                "예: `\"스트레스\": 3`, `\"에너지\": 10`)"
            )
        lines: list[str] = []
        for k in sorted(stats.keys(), key=lambda x: str(x)):
            v = stats[k]
            if isinstance(v, bool):
                lines.append(f"- {k}: {v}")
            elif isinstance(v, (int, float)) and v == v:  # not NaN
                lines.append(f"- {k}: {v}")
            elif isinstance(v, str) and len(v) < 120:
                lines.append(f"- {k}: {v}")
        if not lines:
            return "(stats 객체에 표시 가능한 숫자/짧은 문자열 값이 없음)"
        return "\n".join(lines)

    @staticmethod
    def _format_relationships_block(
        npcs: list[dict[str, Any]],
        player: dict[str, Any],
    ) -> str:
        """NPC별 활성 관계 수치 — LLM 전용(유저 대사에 노출 금지)."""
        rows = build_session_relationship_view(npcs, player)
        if not rows:
            return "(월드에 설정된 관계 스탯 없음 — `relationship_stats` 미설정 NPC)"
        lines: list[str] = []
        for row in rows:
            name = str(row.get("npc_name", ""))
            stats = row.get("stats")
            if not isinstance(stats, dict) or not stats:
                continue
            lines.append(f"### {name}")
            for slug in RELATIONSHIP_STAT_ORDER:
                if slug not in stats:
                    continue
                label = RELATIONSHIP_STAT_LABELS_KO.get(slug, slug)
                lines.append(f"- {label}({slug}): {stats[slug]}/100")
            lines.append("")
        return "\n".join(lines).strip() if lines else "(활성 관계 스탯 없음)"

    def build_system_blocks(
        self,
        world: dict[str, Any],
        player: dict[str, Any],
        npcs: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        cache_reset_flag: str | None = None,
        *,
        turn: int = 0,
        day: int = 1,
        user_message: str = "",
        recent_conversation: list[dict[str, Any]] | None = None,
        pending_event_hints: list[str] | None = None,
    ) -> tuple[str, str]:
        """시스템 프롬프트를 Anthropic 프롬프트 캐시용으로 분리.

        - **static**: 턴마다 거의 동일 → 첫 system 블록에만 ``cache_control: ephemeral`` 권장.
        - **dynamic**: 참가 NPC 선택·턴·기억 등 매 턴 변동. (장소 기반 필터 없음.)

        Returns:
            ``(static, dynamic)`` — 둘 다 strip 된 문자열.
        """
        recent = recent_conversation or []
        cap = self._dialogue_npc_cap(world)
        active_npcs = self._select_npcs_for_dialogue(
            user_message, npcs, recent, cap=cap
        )
        dialogue_names = ", ".join(
            str(n.get("name", "")).strip()
            for n in active_npcs
            if str(n.get("name", "")).strip()
        )
        npc_profiles = self._format_compact_npcs(active_npcs)
        key_memories = self._select_key_memories(memories)

        world_name = world.get("name", "알 수 없는 세계")
        world_display = world.get("name", "")
        player_name = player.get("name", "플레이어")
        stats_block = self._format_player_stats_block(player)
        relationships_block = self._format_relationships_block(npcs, player)

        desc_line, lore_body = self._world_lore_paragraphs(world)
        world_context = ""
        if desc_line or lore_body:
            ctx_parts: list[str] = []
            if desc_line:
                ctx_parts.append(f"## 세계 한 줄 요약\n{desc_line}")
            if lore_body:
                ctx_parts.append(f"## 세계관 설정\n{lore_body}")
            world_context = "\n\n" + "\n\n".join(ctx_parts)

        static_body = f"""너는 {world_name}의 NPC다.

**중요: 현재 세계관은 "{world_display}"입니다. 다른 세계관의 설정을 절대 사용하지 마세요.**{world_context}

## 플레이어
- 이름: {player_name}
- 호칭은 반드시 "{player_name}".

## 응답 규칙 (가장 중요 — 유저 화면이 빈 줄마다 카드로 쪼개짐)
- **빈 줄 한 줄 = 화면 카드 1개.** 한 턴 **블록 합계 최대 5개**(NPC+내레이션). **6개 이상 절대 금지.**
- **이름 없는 내레이션 블록은 한 턴에 최대 1개.** 배경·분위기·동작은 **NPC 줄의 (괄호)** 안에 넣고, 별도 내레이션 블록으로 쪼개지 마세요.
- 짧은 반응·표정·환경마다 빈 줄 넣지 마세요. 한 NPC 블록에 (행동)+대사 2~3문장까지 묶어도 됩니다.
- NPC가 바뀔 때만 빈 줄로 블록을 나눕니다. 첫 줄: **NPC이름** (짧은 행동) 후 대사.
- 한 턴 NPC 1~2명(많아도 3명). 장황한 묘사·반복·장면 나열 금지.
- 진행 안내·플레이어님·시스템 톤 금지.
- **유저에게 보이는 대사에 관계 수치·변화량(호감+5 등)·스탯 이름을 절대 쓰지 마세요.** 수치는 시스템·툴로만 갱신한다.
- **중요: `update_game_state` 툴을 사용하는 경우에도 반드시 같은 응답에 NPC 대사(텍스트)를 포함하세요.**
  - 툴만 보내지 마세요.
  - 대사와 툴을 항상 함께 보내세요.
  - 예외: 시스템 점검·내부 처리 등 극히 드문 경우만 텍스트 생략 가능.

## Tool (update_game_state)
**도구를 사용할 때도 NPC 대사는 반드시 같은 응답에 함께 포함하세요.**
대화에 변화가 있으면 매 턴 사용. 무의미한 한 단어("응"만 등)만 예외.
관계 변화는 아래 「관계 수치」와 상황에 맞게 `relationship_changes`로 갱신(활성 스탯만). new_memories importance: 1~3 일상, 4~6 의미, 7+ 중요 사건.
플레이어 능력·자원 스탯은 `resource_stat_changes`로만 갱신(아래 「플레이어 스탯」 키만). **매 턴 남발 금지** — 연습·훈련·중요한 성과 등 의미 있는 행동에만. 한 턴 change ±5. |change|≥3 또는 `show_card:true`면 유저에게 EventCard로 표시된다. 대사에 스탯 이름·수치를 쓰지 마세요.
관계 스탯 종류: affection, trust, respect, fear, loyalty, romance, disgust, wrath (한 턴 change ±10).
감정 태그: joy, sadness, anger, fear, surprise, trust, neutral
"""
        static = static_body.strip()

        prefix_lines: list[str] = []
        if turn == 0:
            prefix_lines.append("(세션 시작)")
        if cache_reset_flag:
            prefix_lines.append(f"[{cache_reset_flag}]")
        prefix = ("\n".join(prefix_lines) + "\n\n") if prefix_lines else ""

        recent_events_block = ""
        hints = [h.strip() for h in (pending_event_hints or []) if h and h.strip()]
        if hints:
            hints_text = "\n".join(hints)
            recent_events_block = f"""

## 방금 일어난 일 (지난 턴)
{hints_text}

NPC들은 이 변화를 자연스럽게 인지할 수 있습니다.
명시적으로 언급하기보다는 분위기나 대사에 녹여주세요.
"""

        dynamic = f"""{prefix}## 현재 상황
- 이번 턴 중심 NPC (위 프로필을 기준으로 반응; 다른 인물은 필수 아님): {dialogue_names or "(프로필 없음)"}
- 턴: {turn}
- 일차: {day}

## 플레이어 스텟 (저장된 수치를 따른다. LLM이 임의로 변경하지 말 것)
{stats_block}

## 관계 수치 (LLM 전용 — 아래 값을 반응의 기준으로 삼고, 유저 대사에는 숫자·스탯명 노출 금지)
{relationships_block}

## NPC
{npc_profiles if npc_profiles else "(없음)"}

## 중요 기억
{self._format_memories(key_memories)}{recent_events_block}

## 이번 턴 출력 제한 (필수 — 위반 시 UX 깨짐)
- 빈 줄로 나눈 블록 **합계 5개 이하**. 6개 이상 쓰지 마세요.
- **내레이션-only 블록 1개 이하.** 나머지 묘사는 NPC 대사 (괄호) 로 처리.
- 출력이 길어지면 문장을 줄이세요. 블록을 늘리지 마세요.
"""
        return static.strip(), dynamic.strip()

    def build_optimized_prompt(
        self,
        world: dict[str, Any],
        player: dict[str, Any],
        npcs: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        cache_reset_flag: str | None = None,
        *,
        turn: int = 0,
        day: int = 1,
        user_message: str = "",
        recent_conversation: list[dict[str, Any]] | None = None,
    ) -> str:
        """최적화된 시스템 프롬프트 (단일 문자열, 테스트·로깅용)."""
        static, dynamic = self.build_system_blocks(
            world=world,
            player=player,
            npcs=npcs,
            memories=memories,
            cache_reset_flag=cache_reset_flag,
            turn=turn,
            day=day,
            user_message=user_message,
            recent_conversation=recent_conversation,
        )
        parts = [p for p in (static, dynamic) if p]
        return "\n\n".join(parts)

    @staticmethod
    def _speaking_style_from_npc(npc: dict[str, Any]) -> Any:
        if "speaking_style" in npc:
            return npc["speaking_style"]
        if "speech_style" in npc:
            return npc["speech_style"]
        return None

    @staticmethod
    def _truncate_for_prompt(text: str, max_len: int = 200) -> str:
        s = text.strip()
        if len(s) <= max_len:
            return s
        return s[: max_len - 1] + "…"

    def _format_compact_npcs(self, npcs: list[dict[str, Any]]) -> str:
        """세계관에 관계없이 NPC 정보를 포맷팅"""
        lines: list[str] = []
        for npc in npcs:
            name = npc.get("name", "Unknown")
            role = npc.get("role", "")

            info_parts = [name]
            if role:
                info_parts.append(f"({role})")

            major = npc.get("major")
            if isinstance(major, str) and major.strip():
                info_parts.append(f"- {major.strip()}")

            info = " ".join(info_parts)
            lines.append(info)

            details = []

            if "personality" in npc:
                p = npc["personality"]
                if isinstance(p, str) and p.strip():
                    details.append(f"  성격: {self._truncate_for_prompt(p, 300)}")

            bg = npc.get("background")
            if isinstance(bg, str) and bg.strip():
                details.append(f"  배경: {self._truncate_for_prompt(bg, 200)}")
            else:
                desc = npc.get("description")
                if isinstance(desc, str) and desc.strip():
                    details.append(f"  배경: {self._truncate_for_prompt(desc, 200)}")

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

            style = self._speaking_style_from_npc(npc)
            if isinstance(style, str) and style.strip():
                details.append(f"  말투: {style.strip()}")
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
