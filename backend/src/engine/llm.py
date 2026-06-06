"""
ClaudeClient - Anthropic Claude API 통합

LangChain 없이 Claude API를 직접 사용합니다.
Tool Use: 기본 2단계 호출 + Single-Pass(1차에 텍스트 있으면 2차 생략).

TODO: Week 1 Day 5-7에 구현 완성
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from anthropic import Anthropic

from ..utils.config import get_settings
from .relationship_stats import RELATIONSHIP_STAT_ORDER
from ..utils.logger import get_logger
from .context_manager import ContextManager

logger = get_logger(__name__)


# 게임 상태 업데이트 Tool 정의
GAME_STATE_TOOL = {
    "name": "update_game_state",
    "description": (
        "플레이어의 행동에 따른 게임 상태 변경을 제안합니다. "
        "관계 변화, 새 기억, 성격 변화 등을 포함합니다. "
        "반드시 이 도구를 사용하여 상태 변경을 제안하세요. "
        "도구를 사용할 때도 NPC 대사(텍스트)는 같은 assistant 응답에 반드시 함께 포함하세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relationship_changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string", "description": "NPC 이름"},
                        "stat": {
                            "type": "string",
                            "enum": list(RELATIONSHIP_STAT_ORDER),
                            "description": "변경할 관계 수치",
                        },
                        "change": {
                            "type": "number",
                            "description": "변화량 (-10 ~ +10)",
                        },
                        "reason": {"type": "string", "description": "변화 이유"},
                    },
                    "required": ["character", "stat", "change"],
                },
                "description": "관계 수치 변화 목록",
            },
            "new_memories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "기억 내용"},
                        "emotion": {
                            "type": "string",
                            "enum": [
                                "joy",
                                "sadness",
                                "anger",
                                "fear",
                                "surprise",
                                "trust",
                                "neutral",
                            ],
                            "description": "감정 태그",
                        },
                        "importance": {
                            "type": "number",
                            "description": "중요도 (1-10)",
                        },
                    },
                    "required": ["content", "emotion", "importance"],
                },
                "description": "새로 형성된 기억들",
            },
        },
        "required": ["relationship_changes", "new_memories"],
    },
}


class ClaudeClient:
    """Anthropic Claude API 클라이언트 - 올바른 Tool Use 처리"""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        resolved = api_key.strip() if api_key else settings.anthropic_api_key
        self.client = Anthropic(api_key=resolved)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    def rebind_api_key(self, api_key: str | None) -> None:
        """None 이면 설정의 플랫폼 키로 되돌림 (BYOK 제거 후)."""
        settings = get_settings()
        resolved = api_key.strip() if api_key else settings.anthropic_api_key
        self.client = Anthropic(api_key=resolved)

    @staticmethod
    def _system_messages_from_prompt(
        system_prompt: str | tuple[str, str],
    ) -> list[dict[str, Any]]:
        """Anthropic system 파라미터 구성. (static, dynamic)이면 static에만 프롬프트 캐시."""
        if isinstance(system_prompt, tuple):
            static, dynamic = system_prompt
            st = (static or "").strip()
            dy = (dynamic or "").strip()
            blocks: list[dict[str, Any]] = []
            if st:
                blocks.append(
                    {
                        "type": "text",
                        "text": st,
                        "cache_control": {"type": "ephemeral"},
                    }
                )
            if dy:
                blocks.append({"type": "text", "text": dy})
            if not blocks:
                blocks.append(
                    {
                        "type": "text",
                        "text": "",
                        "cache_control": {"type": "ephemeral"},
                    }
                )
            return blocks
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def process_turn(
        self,
        user_input: str,
        system_prompt: str | tuple[str, str],
        conversation_history: list[dict[str, Any]] | None = None,
        *,
        enable_single_pass: bool = True,
    ) -> dict[str, Any]:
        """
        사용자 입력을 처리하고 응답 + 상태 변경을 반환합니다.

        Tool Use 시 기본(2단계):
        1. 1차 호출 → tool_use 응답
        2. tool_result 전달
        3. 2차 호출 → 최종 텍스트 응답

        Single-Pass (``enable_single_pass=True``): 1차 응답에 텍스트가 있으면 2차 생략.

        Args:
            enable_single_pass: True면 1차에 NPC 대사 텍스트가 있을 때 2차 API 호출 생략.

        Returns:
            기존 필드 + ``llm_api_calls`` (1 또는 2).
        """
        # conversation_history에 이미 user_input이 포함되어 있음
        messages = conversation_history or []
        system_messages = self._system_messages_from_prompt(system_prompt)

        tools = self._get_tools()
        tools_str = json.dumps(tools, ensure_ascii=False)
        logger.debug(f"Tools definition: {len(tools_str)} chars (~{len(tools_str)//4} tokens)")

        if isinstance(system_prompt, tuple):
            s_len = len(system_prompt[0] or "")
            d_len = len(system_prompt[1] or "")
            logger.debug(
                "System prompt (split): static=%s dynamic=%s chars (~%s / ~%s tokens)",
                s_len,
                d_len,
                s_len // 4,
                d_len // 4,
            )
        else:
            logger.debug(
                "System prompt: %s chars (~%s tokens)",
                len(system_prompt),
                len(system_prompt) // 4,
            )
        logger.debug(f"User input: {len(user_input)} chars (~{len(user_input)//4} tokens)")
        logger.debug(f"History messages: {len(messages)}")
        logger.debug(f"LLM 1차 호출: {user_input[:50]}...")

        # 1차 호출
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_messages,
            tools=tools,
            messages=messages,
        )
        usage = getattr(response, "usage", None)
        if usage:
            logger.debug(f"1차 input: {getattr(usage, 'input_tokens', 0)} tokens")
            creation = getattr(usage, "cache_creation_input_tokens", 0)
            read = getattr(usage, "cache_read_input_tokens", 0)
            if creation:
                logger.info(f"Cache created: {creation} tokens")
            if read:
                logger.info(f"Cache read: {read} tokens")

        # Tool Use 체크
        if response.stop_reason == "tool_use":
            return self._handle_tool_use(
                response,
                messages,
                system_messages,
                tools,
                enable_single_pass=enable_single_pass,
            )
        else:
            # Tool Use 없이 텍스트만 온 경우
            text = self._extract_text(response)
            in_tokens, out_tokens = self._extract_usage(response)
            seg = self._usage_segment_from_response(response)
            return {
                "response": text,
                "state_changes": {},
                "tool_used": False,
                "input_tokens": in_tokens,
                "input_tokens_first": in_tokens,
                "input_tokens_second": 0,
                "output_tokens": out_tokens,
                "cache_creation_tokens": seg["cache_creation_tokens"],
                "cache_read_tokens": seg["cache_read_tokens"],
                "usage_segments": [seg],
                "llm_api_calls": 1,
            }

    def process_turn_stream(
        self,
        user_input: str,
        system_prompt: str | tuple[str, str],
        conversation_history: list[dict[str, Any]] | None = None,
        *,
        enable_single_pass: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """process_turn 의 스트리밍 버전 (옵션 A: 1차만 스트림).

        Yields 두 종류의 이벤트:
            - {"type": "delta", "text": str}: 1차 응답의 텍스트 청크.
            - {"type": "done", "result": {...}}: 최종 결과 (process_turn 반환 dict 와 동일 형식).

        동작 정책:
            - 1차 호출만 stream 으로 실행. text_delta 만 흘려보내고 tool_use 입력은 누적.
            - Single-Pass: 1차 응답에 텍스트가 있으면 그대로 done.
            - Fallback: 1차에 텍스트 없고 stop_reason 이 tool_use → 비스트림 2차 호출 후 done.
        """
        messages = conversation_history or []
        system_messages = self._system_messages_from_prompt(system_prompt)
        tools = self._get_tools()

        logger.debug("LLM 1차 stream 호출: %s...", user_input[:50])

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_messages,
            tools=tools,
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                if chunk:
                    yield {"type": "delta", "text": chunk}
            final = stream.get_final_message()

        if final.stop_reason == "tool_use":
            result = self._handle_tool_use(
                final,
                messages,
                system_messages,
                tools,
                enable_single_pass=enable_single_pass,
            )
        else:
            text = self._extract_text(final)
            in_tokens, out_tokens = self._extract_usage(final)
            seg = self._usage_segment_from_response(final)
            result = {
                "response": text,
                "state_changes": {},
                "tool_used": False,
                "input_tokens": in_tokens,
                "input_tokens_first": in_tokens,
                "input_tokens_second": 0,
                "output_tokens": out_tokens,
                "cache_creation_tokens": seg["cache_creation_tokens"],
                "cache_read_tokens": seg["cache_read_tokens"],
                "usage_segments": [seg],
                "llm_api_calls": 1,
            }

        yield {"type": "done", "result": result}

    def _handle_tool_use(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        system_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        enable_single_pass: bool = True,
    ) -> dict[str, Any]:
        """Tool Use 응답을 처리하고, 필요 시 2차 호출 수행."""
        # Tool Use 블록 추출
        tool_use_block = None
        state_changes: dict[str, Any] = {}

        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block
                state_changes = block.input
                break

        if not tool_use_block:
            logger.warning("tool_use stop_reason이지만 tool_use 블록을 찾을 수 없음")
            in0, out0 = self._extract_usage(response)
            seg = self._usage_segment_from_response(response)
            return {
                "response": self._extract_text(response),
                "state_changes": {},
                "tool_used": False,
                "input_tokens": in0,
                "input_tokens_first": in0,
                "input_tokens_second": 0,
                "output_tokens": out0,
                "cache_creation_tokens": seg["cache_creation_tokens"],
                "cache_read_tokens": seg["cache_read_tokens"],
                "usage_segments": [seg],
                "llm_api_calls": 1,
            }

        logger.debug(f"Tool Use 감지: {tool_use_block.name}")
        logger.debug(f"State Changes: {json.dumps(state_changes, ensure_ascii=False)}")

        # 1차 응답에 텍스트가 있으면 fallback으로 보관
        first_text = self._extract_text(response)

        # Single-Pass: 같은 응답에 NPC 대사가 있으면 2차 호출 생략
        if enable_single_pass and first_text.strip():
            logger.info(
                "✅ 1차 응답에 text 있음 → 2차 스킵 (Single-Pass Tool Use)"
            )
            in1, out1 = self._extract_usage(response)
            seg = self._usage_segment_from_response(response)
            return {
                "response": first_text.strip(),
                "state_changes": state_changes,
                "tool_used": True,
                "input_tokens": in1,
                "input_tokens_first": in1,
                "input_tokens_second": 0,
                "output_tokens": out1,
                "cache_creation_tokens": seg["cache_creation_tokens"],
                "cache_read_tokens": seg["cache_read_tokens"],
                "usage_segments": [seg],
                "llm_api_calls": 1,
            }

        logger.info("⚠️ 1차 응답에 text 없음 → 2차 호출 (Fallback)")

        # Tool Result 생성 (간소하게)
        tool_result = {
            "type": "tool_result",
            "tool_use_id": tool_use_block.id,
            "content": "Success",
        }

        # 2차 호출용 메시지 구성 — Layer 1과 동일한 최근 턴 수 (ContextManager.KEEP_RECENT_TURNS)
        recent_count = ContextManager.KEEP_RECENT_TURNS * 2
        messages_recent = messages[-recent_count:] if len(messages) > recent_count else messages.copy()
        
        messages_for_2nd = messages_recent.copy()
        
        tool_use_payload = {
            "type": "tool_use",
            "id": tool_use_block.id,
            "name": tool_use_block.name,
            "input": tool_use_block.input,
        }
        messages_for_2nd.append({"role": "assistant", "content": [tool_use_payload]})
        messages_for_2nd.append({"role": "user", "content": [tool_result]})

        logger.debug(f"LLM 2차 호출 (Layer 1만: {len(messages_recent)}개 + Tool Result)...")

        final_response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_messages,
            tools=tools,
            messages=messages_for_2nd,
        )
        usage_2 = getattr(final_response, "usage", None)
        if usage_2:
            logger.debug(f"2차 input: {getattr(usage_2, 'input_tokens', 0)} tokens")
            creation = getattr(usage_2, "cache_creation_input_tokens", 0)
            read = getattr(usage_2, "cache_read_input_tokens", 0)
            if creation:
                logger.info(f"Cache created (2차): {creation} tokens")
            if read:
                logger.info(f"Cache read (2차): {read} tokens")
        usage_2 = getattr(final_response, "usage", None)
        if usage_2:
            logger.debug(f"2차 input: {getattr(usage_2, 'input_tokens', 0)} tokens")
            first_usage = getattr(response, "usage", None)
            total = (
                getattr(first_usage, "input_tokens", 0)
                + getattr(usage_2, "input_tokens", 0)
            )
            logger.debug(f"총 input: {total} tokens")

        final_text = self._extract_text(final_response)

        # 2차 응답이 비었으면 1차 텍스트를 fallback으로 사용
        if not final_text and first_text:
            logger.debug("2차 응답 비어있음 → 1차 텍스트를 fallback으로 사용")
            final_text = first_text

        in1, out1 = self._extract_usage(response)
        in2, out2 = self._extract_usage(final_response)
        creation1 = getattr(response.usage, "cache_creation_input_tokens", 0) if getattr(response, "usage", None) else 0
        creation2 = getattr(final_response.usage, "cache_creation_input_tokens", 0) if getattr(final_response, "usage", None) else 0
        read1 = getattr(response.usage, "cache_read_input_tokens", 0) if getattr(response, "usage", None) else 0
        read2 = getattr(final_response.usage, "cache_read_input_tokens", 0) if getattr(final_response, "usage", None) else 0

        seg1 = {
            "input_tokens": in1,
            "output_tokens": out1,
            "cache_creation_tokens": creation1,
            "cache_read_tokens": read1,
        }
        seg2 = {
            "input_tokens": in2,
            "output_tokens": out2,
            "cache_creation_tokens": creation2,
            "cache_read_tokens": read2,
        }
        return {
            "response": final_text,
            "state_changes": state_changes,
            "tool_used": True,
            "input_tokens": in1 + in2,
            "input_tokens_first": in1,
            "input_tokens_second": in2,
            "output_tokens": out1 + out2,
            "cache_creation_tokens": creation1 + creation2,
            "cache_read_tokens": read1 + read2,
            "usage_segments": [seg1, seg2],
            "llm_api_calls": 2,
        }

    @staticmethod
    def _usage_segment_from_response(response: Any) -> dict[str, int]:
        """Messages API usage → UsageTracker.log_turn_anthropic용 세그먼트."""
        u = getattr(response, "usage", None)
        if not u:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
            }
        return {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_creation_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        }

    def _extract_text(self, response: Any) -> str:
        """응답에서 모든 text 블록을 순서대로 이어 붙임 (Single-Pass 대비)."""
        parts: list[str] = []
        for block in response.content:
            if block.type == "text" and getattr(block, "text", None):
                parts.append(block.text)
        return "\n\n".join(parts) if parts else ""

    def _extract_usage(self, response: Any) -> tuple[int, int]:
        """응답에서 사용된 토큰 수 추출"""
        usage = getattr(response, "usage", None)
        if not usage:
            return 0, 0
        return getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0

    def _get_tools(self) -> list[dict[str, Any]]:
        """Tool 정의를 일관되게 반환"""
        return [GAME_STATE_TOOL]
