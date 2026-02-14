"""
ClaudeClient 유닛 테스트 (Mock 기반)

실제 API를 호출하지 않고 Claude API 통합 로직을 검증합니다.
핵심 검증 사항:
  - Tool Use 2단계 호출이 올바르게 수행되는지
  - 일반 텍스트 응답 처리
  - API 에러 시 예외 처리
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.engine.llm import ClaudeClient, GAME_STATE_TOOL


# ---------------------------------------------------------------------------
# Helper: Anthropic API 응답을 흉내내는 가짜 객체들
# ---------------------------------------------------------------------------


@dataclass
class FakeTextBlock:
    """텍스트 블록"""
    type: str = "text"
    text: str = ""


@dataclass
class FakeToolUseBlock:
    """Tool Use 블록"""
    type: str = "tool_use"
    id: str = "toolu_test_123"
    name: str = "update_game_state"
    input: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.input is None:
            self.input = {
                "relationship_changes": [
                    {"character": "엘레나", "stat": "affection", "change": 5, "reason": "선물"}
                ],
                "new_memories": [
                    {"content": "꽃을 선물 받았다", "emotion": "joy", "importance": 7}
                ],
            }


@dataclass
class FakeResponse:
    """Anthropic Messages API 응답"""
    content: list[Any] = None  # type: ignore[assignment]
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = [FakeTextBlock(text="안녕하세요!")]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def claude_client() -> ClaudeClient:
    """Mock된 ClaudeClient 생성 (실제 API 키 불필요)"""
    with patch("backend.src.engine.llm.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            anthropic_api_key="sk-ant-test-fake-key",
            llm_model="claude-sonnet-4-5-20250929",
            llm_max_tokens=2000,
        )
        with patch("backend.src.engine.llm.Anthropic") as mock_anthropic_cls:
            client = ClaudeClient()
            # mock_anthropic_cls()가 반환한 인스턴스가 client.client
            client.client = mock_anthropic_cls.return_value
            return client


# ---------------------------------------------------------------------------
# 1. Tool Use 2단계 호출 테스트
# ---------------------------------------------------------------------------


class TestToolUseHandling:
    """Tool Use 응답 처리 검증"""

    def test_tool_use_triggers_second_call(self, claude_client: ClaudeClient) -> None:
        """Tool Use 응답 시 2차 호출이 실행되는지 확인"""
        tool_input = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 5, "reason": "선물"}
            ],
            "new_memories": [
                {"content": "꽃을 선물 받았다", "emotion": "joy", "importance": 7}
            ],
        }

        # 1차 응답: tool_use
        first_response = FakeResponse(
            content=[
                FakeTextBlock(text=""),
                FakeToolUseBlock(input=tool_input),
            ],
            stop_reason="tool_use",
        )

        # 2차 응답: 최종 텍스트
        second_response = FakeResponse(
            content=[FakeTextBlock(text="아, 아름다운 꽃이네요! 고마워요.")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        result = claude_client.process_turn(
            user_input="엘레나에게 꽃을 선물한다",
            system_prompt="너는 NPC야.",
        )

        # 2번 호출되었는지 확인
        assert claude_client.client.messages.create.call_count == 2

    def test_tool_use_returns_state_changes(self, claude_client: ClaudeClient) -> None:
        """Tool Use 시 state_changes가 올바르게 반환되는지"""
        tool_input = {
            "relationship_changes": [
                {"character": "벨라", "stat": "trust", "change": 3, "reason": "도움"}
            ],
            "new_memories": [
                {"content": "벨라를 도와줬다", "emotion": "trust", "importance": 6}
            ],
        }

        first_response = FakeResponse(
            content=[FakeToolUseBlock(input=tool_input)],
            stop_reason="tool_use",
        )
        second_response = FakeResponse(
            content=[FakeTextBlock(text="...고, 고마워.")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        result = claude_client.process_turn(
            user_input="벨라를 도와준다",
            system_prompt="너는 NPC야.",
        )

        assert result["tool_used"] is True
        assert result["state_changes"] == tool_input
        assert result["state_changes"]["relationship_changes"][0]["character"] == "벨라"
        assert result["state_changes"]["relationship_changes"][0]["change"] == 3
        assert len(result["state_changes"]["new_memories"]) == 1

    def test_tool_use_returns_final_text(self, claude_client: ClaudeClient) -> None:
        """Tool Use 시 최종 텍스트가 2차 응답에서 나오는지"""
        first_response = FakeResponse(
            content=[FakeToolUseBlock()],
            stop_reason="tool_use",
        )
        second_response = FakeResponse(
            content=[FakeTextBlock(text="고마워요, 정말 예쁜 꽃이에요!")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        result = claude_client.process_turn(
            user_input="꽃을 선물한다",
            system_prompt="너는 NPC야.",
        )

        assert result["response"] == "고마워요, 정말 예쁜 꽃이에요!"

    def test_second_call_includes_tool_result(self, claude_client: ClaudeClient) -> None:
        """2차 호출 시 messages에 tool_result가 포함되는지"""
        first_response = FakeResponse(
            content=[FakeToolUseBlock(id="toolu_abc123")],
            stop_reason="tool_use",
        )
        second_response = FakeResponse(
            content=[FakeTextBlock(text="네, 감사합니다!")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        claude_client.process_turn(
            user_input="인사한다",
            system_prompt="너는 NPC야.",
        )

        # 2차 호출의 messages 인자 확인
        second_call_kwargs = claude_client.client.messages.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")

        # messages 구조: [..., {role: assistant, content: [tool_use]}, {role: user, content: [tool_result]}]
        last_msg = messages[-1]
        assert last_msg["role"] == "user"
        assert isinstance(last_msg["content"], list)
        assert last_msg["content"][0]["type"] == "tool_result"
        assert last_msg["content"][0]["tool_use_id"] == "toolu_abc123"

    def test_second_call_includes_assistant_content(self, claude_client: ClaudeClient) -> None:
        """2차 호출 시 assistant의 원래 content(tool_use 포함)가 유지되는지"""
        tool_block = FakeToolUseBlock(id="toolu_xyz789")
        first_response = FakeResponse(
            content=[tool_block],
            stop_reason="tool_use",
        )
        second_response = FakeResponse(
            content=[FakeTextBlock(text="알겠어요.")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        claude_client.process_turn(
            user_input="뭔가 한다",
            system_prompt="시스템",
        )

        second_call_kwargs = claude_client.client.messages.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")

        # assistant 메시지에 원래 content가 들어있는지 확인
        assistant_msg = messages[-2]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] == first_response.content


# ---------------------------------------------------------------------------
# 2. 일반 텍스트 응답 처리 테스트
# ---------------------------------------------------------------------------


class TestTextOnlyResponse:
    """Tool Use 없이 텍스트만 온 경우"""

    def test_text_only_response(self, claude_client: ClaudeClient) -> None:
        """일반 텍스트 응답 처리"""
        response = FakeResponse(
            content=[FakeTextBlock(text="안녕하세요, 반가워요!")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(return_value=response)

        result = claude_client.process_turn(
            user_input="안녕!",
            system_prompt="너는 NPC야.",
        )

        assert result["response"] == "안녕하세요, 반가워요!"
        assert result["state_changes"] == {}
        assert result["tool_used"] is False

    def test_text_only_single_api_call(self, claude_client: ClaudeClient) -> None:
        """텍스트만 올 때 API를 1번만 호출하는지"""
        response = FakeResponse(
            content=[FakeTextBlock(text="네!")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(return_value=response)

        claude_client.process_turn(
            user_input="테스트",
            system_prompt="시스템",
        )

        assert claude_client.client.messages.create.call_count == 1

    def test_empty_text_response(self, claude_client: ClaudeClient) -> None:
        """텍스트 블록이 없는 응답 처리 (빈 문자열 반환)"""
        # content에 텍스트 블록이 없는 극단적 케이스
        response = FakeResponse(
            content=[],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(return_value=response)

        result = claude_client.process_turn(
            user_input="...",
            system_prompt="시스템",
        )

        assert result["response"] == ""
        assert result["tool_used"] is False


# ---------------------------------------------------------------------------
# 3. API 에러 처리 테스트
# ---------------------------------------------------------------------------


class TestApiErrorHandling:
    """API 에러 발생 시 동작 검증"""

    def test_api_error_propagates(self, claude_client: ClaudeClient) -> None:
        """API 에러가 발생하면 예외가 전파되는지"""
        claude_client.client.messages.create = MagicMock(
            side_effect=Exception("API rate limit exceeded")
        )

        with pytest.raises(Exception, match="API rate limit exceeded"):
            claude_client.process_turn(
                user_input="테스트",
                system_prompt="시스템",
            )

    def test_second_call_error_propagates(self, claude_client: ClaudeClient) -> None:
        """1차 호출은 성공하고 2차 호출에서 에러 발생 시"""
        first_response = FakeResponse(
            content=[FakeToolUseBlock()],
            stop_reason="tool_use",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, Exception("Network timeout")]
        )

        with pytest.raises(Exception, match="Network timeout"):
            claude_client.process_turn(
                user_input="테스트",
                system_prompt="시스템",
            )

    def test_anthropic_auth_error(self, claude_client: ClaudeClient) -> None:
        """인증 에러 시 예외 전파"""
        from anthropic import AuthenticationError

        claude_client.client.messages.create = MagicMock(
            side_effect=AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401, headers={}),
                body={"error": {"message": "Invalid API key"}},
            )
        )

        with pytest.raises(AuthenticationError):
            claude_client.process_turn(
                user_input="테스트",
                system_prompt="시스템",
            )


# ---------------------------------------------------------------------------
# 4. 엣지 케이스 테스트
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """특수 상황 처리"""

    def test_tool_use_stop_reason_but_no_tool_block(self, claude_client: ClaudeClient) -> None:
        """stop_reason이 tool_use인데 실제 tool_use 블록이 없는 경우"""
        response = FakeResponse(
            content=[FakeTextBlock(text="뭔가 이상합니다...")],
            stop_reason="tool_use",  # tool_use라고 하는데
        )

        claude_client.client.messages.create = MagicMock(return_value=response)

        result = claude_client.process_turn(
            user_input="테스트",
            system_prompt="시스템",
        )

        # 이 경우 텍스트 응답으로 폴백, 1회만 호출
        assert result["response"] == "뭔가 이상합니다..."
        assert result["state_changes"] == {}
        assert result["tool_used"] is False
        assert claude_client.client.messages.create.call_count == 1

    def test_conversation_history_passed_correctly(self, claude_client: ClaudeClient) -> None:
        """대화 히스토리가 올바르게 전달되는지"""
        response = FakeResponse(
            content=[FakeTextBlock(text="네!")],
            stop_reason="end_turn",
        )
        claude_client.client.messages.create = MagicMock(return_value=response)

        history = [
            {"role": "user", "content": "이전 대화"},
            {"role": "assistant", "content": "이전 응답"},
        ]

        claude_client.process_turn(
            user_input="새 입력",
            system_prompt="시스템",
            conversation_history=history.copy(),
        )

        call_kwargs = claude_client.client.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")

        # 히스토리 + 새 입력 = 3개
        assert len(messages) == 3
        assert messages[0]["content"] == "이전 대화"
        assert messages[1]["content"] == "이전 응답"
        assert messages[2]["content"] == "새 입력"

    def test_game_state_tool_definition_correct(self) -> None:
        """GAME_STATE_TOOL 정의가 올바른 구조인지"""
        assert GAME_STATE_TOOL["name"] == "update_game_state"
        assert "input_schema" in GAME_STATE_TOOL
        schema = GAME_STATE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "relationship_changes" in schema["properties"]
        assert "new_memories" in schema["properties"]
        assert schema["required"] == ["relationship_changes", "new_memories"]

    def test_tool_input_contains_relationship_and_memory(self, claude_client: ClaudeClient) -> None:
        """Tool Use input에서 relationship_changes와 new_memories가 모두 추출되는지"""
        tool_input = {
            "relationship_changes": [
                {"character": "루아", "stat": "affection", "change": 8, "reason": "장난"},
                {"character": "엘레나", "stat": "trust", "change": -2, "reason": "실수"},
            ],
            "new_memories": [
                {"content": "루아와 즐겁게 장난쳤다", "emotion": "joy", "importance": 6},
                {"content": "엘레나 앞에서 실수했다", "emotion": "fear", "importance": 8},
            ],
        }

        first_response = FakeResponse(
            content=[FakeToolUseBlock(input=tool_input)],
            stop_reason="tool_use",
        )
        second_response = FakeResponse(
            content=[FakeTextBlock(text="하하, 재밌었어!")],
            stop_reason="end_turn",
        )

        claude_client.client.messages.create = MagicMock(
            side_effect=[first_response, second_response]
        )

        result = claude_client.process_turn(
            user_input="루아와 장난친다",
            system_prompt="시스템",
        )

        changes = result["state_changes"]
        assert len(changes["relationship_changes"]) == 2
        assert len(changes["new_memories"]) == 2
        assert changes["relationship_changes"][0]["character"] == "루아"
        assert changes["relationship_changes"][1]["character"] == "엘레나"
