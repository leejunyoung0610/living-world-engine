#!/usr/bin/env python3
"""
Claude API 키 테스트 스크립트

사용법:
  poetry run python backend/scripts/test_claude_api.py

환경 변수:
  ANTHROPIC_API_KEY - Claude API 키
"""

import os
import sys
import json

# .env 파일 로드
from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic


def test_basic_call() -> bool:
    """기본 API 호출 테스트"""
    print("🧪 Test 1: Basic API Call")
    print("-" * 50)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다!")
        print("   .env 파일을 생성하거나 환경 변수를 설정하세요:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        return False

    try:
        client = Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=100,
            messages=[{"role": "user", "content": "안녕! 간단히 인사만 해줘."}],
        )

        response_text = message.content[0].text
        print("✅ API 호출 성공!")
        print(f"📝 응답: {response_text}")
        print()
        return True

    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        return False


def test_tool_use() -> bool:
    """Tool Use (Function Calling) 테스트 - 게임 엔진의 핵심"""
    print("🧪 Test 2: Tool Use (Function Calling)")
    print("-" * 50)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ API 키가 없습니다.")
        return False

    try:
        client = Anthropic(api_key=api_key)

        # 게임 엔진에서 실제 사용할 Tool 정의
        tools = [
            {
                "name": "update_game_state",
                "description": "게임 상태를 업데이트합니다. 관계 변화, 새 기억, 성격 변화를 포함합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "relationship_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "character": {"type": "string"},
                                    "stat": {"type": "string"},
                                    "change": {"type": "number"},
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
                                    "content": {"type": "string"},
                                    "emotion": {"type": "string"},
                                    "importance": {"type": "number"},
                                },
                                "required": ["content", "emotion", "importance"],
                            },
                            "description": "새로 형성된 기억들",
                        },
                    },
                    "required": ["relationship_changes", "new_memories"],
                },
            }
        ]

        # 1차 호출 (tool_use 발생 예상)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            system="너는 판타지 RPG 게임의 NPC 아리아야. 플레이어의 행동에 반응하고, update_game_state 도구를 사용해서 게임 상태를 업데이트해.",
            tools=tools,
            messages=[
                {"role": "user", "content": "아리아에게 아름다운 야생화 다발을 선물한다."}
            ],
        )

        print(f"📤 Stop Reason: {response.stop_reason}")

        if response.stop_reason == "tool_use":
            print("✅ Tool Use 발생!")

            # Tool Use 블록 추출
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_use_block = block
                    break

            if tool_use_block:
                print(f"🔧 Tool Name: {tool_use_block.name}")
                print(f"📊 Tool Input: {json.dumps(tool_use_block.input, ensure_ascii=False, indent=2)}")

                # 2차 호출 (tool_result 반환)
                final_response = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=500,
                    system="너는 판타지 RPG 게임의 NPC 아리아야. 플레이어의 행동에 자연스럽게 반응해.",
                    tools=tools,
                    messages=[
                        {
                            "role": "user",
                            "content": "아리아에게 아름다운 야생화 다발을 선물한다.",
                        },
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_block.id,
                                    "content": json.dumps(
                                        {
                                            "success": True,
                                            "message": "상태가 업데이트되었습니다.",
                                        }
                                    ),
                                }
                            ],
                        },
                    ],
                )

                # 최종 텍스트 추출
                final_text = ""
                for block in final_response.content:
                    if block.type == "text":
                        final_text = block.text
                        break

                print("✅ 최종 응답 받음!")
                print(f"📝 응답: {final_text}")
                print()
                return True
        else:
            # Tool Use 없이 텍스트만 온 경우
            text = ""
            for block in response.content:
                if block.type == "text":
                    text = block.text
                    break
            print("⚠️  Tool Use가 발생하지 않았습니다.")
            print(f"📝 텍스트 응답: {text}")
            print()
            return True

    except Exception as e:
        print(f"❌ Tool Use 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_long_conversation() -> bool:
    """긴 대화 컨텍스트 테스트"""
    print("🧪 Test 3: Long Conversation Context")
    print("-" * 50)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ API 키가 없습니다.")
        return False

    try:
        client = Anthropic(api_key=api_key)

        messages = [
            {"role": "user", "content": "내 이름은 철수야. 나는 정크 등급이야."},
            {
                "role": "assistant",
                "content": "안녕하세요, 철수님! 정크 등급이시군요. 아카데미에서 힘든 일이 많으시겠어요.",
            },
            {"role": "user", "content": "내 이름이 뭐고, 내 등급이 뭐라고 했지?"},
        ]

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            messages=messages,
        )

        response_text = response.content[0].text

        if "철수" in response_text and "정크" in response_text:
            print("✅ 대화 컨텍스트를 완벽히 기억합니다!")
            print(f"📝 응답: {response_text}")
            print()
            return True
        elif "철수" in response_text:
            print("✅ 이름은 기억합니다! (등급은 언급하지 않음)")
            print(f"📝 응답: {response_text}")
            print()
            return True
        else:
            print("⚠️  컨텍스트를 기억하지 못했습니다.")
            print(f"📝 응답: {response_text}")
            print()
            return False

    except Exception as e:
        print(f"❌ 긴 대화 테스트 실패: {e}")
        return False


def main() -> int:
    """메인 테스트 실행"""
    print()
    print("=" * 50)
    print("🎮 Living World Engine - Claude API 테스트")
    print("=" * 50)
    print()

    results: list[tuple[str, bool]] = []

    # Test 1: Basic Call
    results.append(("Basic API Call", test_basic_call()))

    # Test 2: Tool Use (게임 엔진 핵심)
    results.append(("Tool Use (Game State)", test_tool_use()))

    # Test 3: Long Conversation
    results.append(("Long Conversation", test_long_conversation()))

    # 결과 요약
    print("=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print()
    if all_passed:
        print("🎉 모든 테스트 통과! 개발을 시작할 수 있습니다.")
        return 0
    else:
        print("⚠️  일부 테스트 실패. .env 파일의 API 키를 확인하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
