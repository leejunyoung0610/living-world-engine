"""
ClaudeClient - Anthropic Claude API 통합

LangChain 없이 Claude API를 직접 사용합니다.
올바른 Tool Use 2단계 호출을 구현합니다.

TODO: Week 1 Day 5-7에 구현 완성
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from ..utils.config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


# 게임 상태 업데이트 Tool 정의
GAME_STATE_TOOL = {
    "name": "update_game_state",
    "description": (
        "플레이어의 행동에 따른 게임 상태 변경을 제안합니다. "
        "관계 변화, 새 기억, 성격 변화 등을 포함합니다. "
        "반드시 이 도구를 사용하여 상태 변경을 제안하세요."
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
                            "enum": ["affection", "trust", "respect", "fear", "loyalty", "romance"],
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

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    def process_turn(
        self,
        user_input: str,
        system_prompt: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        사용자 입력을 처리하고 응답 + 상태 변경을 반환합니다.

        올바른 2단계 Tool Use 처리:
        1. 1차 호출 → tool_use 응답
        2. tool 실행 + tool_result 생성
        3. 2차 호출 → 최종 텍스트 응답

        Args:
            user_input: 현재 턴의 사용자 입력
            system_prompt: 시스템 프롬프트
            conversation_history: 최적화된 대화 히스토리 (user_input 이미 포함됨)

        Returns:
            {
                "response": str,           # NPC의 텍스트 응답
                "state_changes": dict,     # 상태 변경 데이터
                "tool_used": bool,         # Tool Use 발생 여부
                "input_tokens": int,
                "output_tokens": int,
            }
        """
        # conversation_history에 이미 user_input이 포함되어 있음
        messages = conversation_history or []
        system_messages = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        tools = self._get_tools()
        tools_str = json.dumps(tools, ensure_ascii=False)
        logger.debug(f"Tools definition: {len(tools_str)} chars (~{len(tools_str)//4} tokens)")

        logger.debug(f"System prompt: {len(system_prompt)} chars (~{len(system_prompt)//4} tokens)")
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
            return self._handle_tool_use(response, messages, system_messages, tools)
        else:
            # Tool Use 없이 텍스트만 온 경우
            text = self._extract_text(response)
            in_tokens, out_tokens = self._extract_usage(response)
            return {
                "response": text,
                "state_changes": {},
                "tool_used": False,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
            }

    def _handle_tool_use(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        system_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Tool Use 응답을 처리하고 2차 호출 수행"""
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
            return {
                "response": self._extract_text(response),
                "state_changes": {},
                "tool_used": False,
            }

        logger.debug(f"Tool Use 감지: {tool_use_block.name}")
        logger.debug(f"State Changes: {json.dumps(state_changes, ensure_ascii=False)}")

        # 1차 응답에 텍스트가 있으면 fallback으로 보관
        first_text = self._extract_text(response)

        # Tool Result 생성 (간소하게)
        tool_result = {
            "type": "tool_result",
            "tool_use_id": tool_use_block.id,
            "content": "Success",
        }

        # 2차 호출용 메시지 (기존 messages 복사 + tool_use/tool_result 추가)
        # 기존 messages를 수정하지 않고 새 리스트 생성
        messages_for_2nd = messages.copy()
        
        tool_use_payload = {
            "type": "tool_use",
            "id": tool_use_block.id,
            "name": tool_use_block.name,
            "input": tool_use_block.input,
        }
        messages_for_2nd.append({"role": "assistant", "content": [tool_use_payload]})
        messages_for_2nd.append({"role": "user", "content": [tool_result]})

        logger.debug("LLM 2차 호출 (Tool Result 포함)...")

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

        return {
            "response": final_text,
            "state_changes": state_changes,
            "tool_used": True,
            "input_tokens": in1 + in2,
            "output_tokens": out1 + out2,
            "cache_creation_tokens": creation1 + creation2,
            "cache_read_tokens": read1 + read2,
        }

    def _extract_text(self, response: Any) -> str:
        """응답에서 텍스트 블록 추출"""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _extract_usage(self, response: Any) -> tuple[int, int]:
        """응답에서 사용된 토큰 수 추출"""
        usage = getattr(response, "usage", None)
        if not usage:
            return 0, 0
        return getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0

    def _get_tools(self) -> list[dict[str, Any]]:
        """Tool 정의를 일관되게 반환"""
        return [GAME_STATE_TOOL]
