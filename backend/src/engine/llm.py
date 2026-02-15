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
                            "enum": ["affection", "trust", "respect", "fear"],
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

        Returns:
            {
                "response": str,           # NPC의 텍스트 응답
                "state_changes": dict,     # 상태 변경 데이터
                "tool_used": bool,         # Tool Use 발생 여부
            }
        """
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_input})

        logger.debug(f"LLM 1차 호출: {user_input[:50]}...")

        # 1차 호출
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            tools=[GAME_STATE_TOOL],
            messages=messages,
        )

        # Tool Use 체크
        if response.stop_reason == "tool_use":
            return self._handle_tool_use(response, messages, system_prompt)
        else:
            # Tool Use 없이 텍스트만 온 경우
            text = self._extract_text(response)
            return {
                "response": text,
                "state_changes": {},
                "tool_used": False,
            }

    def _handle_tool_use(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        system_prompt: str,
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

        # Tool Result 생성 — 대사 생성을 유도하는 메시지 포함
        tool_result = {
            "type": "tool_result",
            "tool_use_id": tool_use_block.id,
            "content": json.dumps(
                {
                    "success": True,
                    "message": "상태가 업데이트되었습니다. 이제 NPC의 대사로 응답하세요.",
                },
                ensure_ascii=False,
            ),
        }

        # 2차 호출 (Tool Result 포함)
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": [tool_result]})

        logger.debug("LLM 2차 호출 (Tool Result 포함)...")

        final_response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            tools=[GAME_STATE_TOOL],
            messages=messages,
        )

        final_text = self._extract_text(final_response)

        # 2차 응답이 비었으면 1차 텍스트를 fallback으로 사용
        if not final_text and first_text:
            logger.debug("2차 응답 비어있음 → 1차 텍스트를 fallback으로 사용")
            final_text = first_text

        return {
            "response": final_text,
            "state_changes": state_changes,
            "tool_used": True,
        }

    def _extract_text(self, response: Any) -> str:
        """응답에서 텍스트 블록 추출"""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
