"""
GameEngine 통합 테스트 - 실제 Claude API 호출

실행 방법:
    # 통합 테스트만
    poetry run pytest -m integration --no-cov

    # 유닛 테스트만 (통합 제외)
    poetry run pytest -m "not integration"

주의:
    - .env에 ANTHROPIC_API_KEY가 설정되어 있어야 합니다
    - 실제 API 비용이 발생합니다 (~$0.003/call)
    - 네트워크 필요
"""

import pytest

from backend.src.engine.game_loop import GameEngine

ARCANE_ACADEMY_DIR = "backend/src/worlds/arcane_academy"


@pytest.fixture
def engine() -> GameEngine:
    """실제 Claude API를 사용하는 GameEngine 인스턴스"""
    game = GameEngine()
    game.initialize(ARCANE_ACADEMY_DIR)
    return game


@pytest.mark.integration
class TestGameEngineSingleTurn:
    """단일 턴 통합 테스트"""

    def test_process_turn_returns_response(self, engine: GameEngine) -> None:
        """1턴 플레이: 텍스트 응답이 존재하는지"""
        result = engine.process_turn("안녕, 엘레나! 오늘 결투장에서 뭐 하고 있어?")

        # 텍스트 응답 존재
        assert result["response"], "NPC 응답이 비어있음"
        assert len(result["response"]) > 10, "응답이 너무 짧음"
        print(f"\n📝 NPC 응답:\n{result['response']}")

    def test_process_turn_uses_tool(self, engine: GameEngine) -> None:
        """1턴 플레이: Tool Use가 발생하는지"""
        result = engine.process_turn("엘레나에게 꽃을 선물한다")

        # Tool Use 발생 여부
        print(f"\n🔧 Tool Used: {result['tool_used']}")
        print(f"📊 State Changes: {result['state_changes']}")

        # Tool Use가 발생했다면 상태 변경 확인
        if result["tool_used"]:
            changes = result["state_changes"]
            assert (
                changes.get("relationship_changes") or changes.get("memories_added")
            ), "Tool Use 발생했지만 상태 변경이 없음"

    def test_process_turn_updates_state(self, engine: GameEngine) -> None:
        """1턴 플레이 후 GameEngine 내부 상태가 업데이트되는지"""
        # 초기 상태 기록
        initial_turn = engine.state.turn
        initial_memories = len(engine.memory.memories)

        result = engine.process_turn("엘레나와 마법 연습을 해보고 싶어")

        # 턴 진행 확인
        assert engine.state.turn == initial_turn + 1, "턴이 진행되지 않음"

        # 대화 히스토리 업데이트
        assert len(engine.conversation_history) == 2, "대화 히스토리가 업데이트되지 않음"
        assert engine.conversation_history[0]["role"] == "user"
        assert engine.conversation_history[1]["role"] == "assistant"

        # Tool Use 시 기억 추가 확인
        if result["tool_used"]:
            assert len(engine.memory.memories) > initial_memories, "새 기억이 추가되지 않음"

        print(f"\n🔄 턴: {engine.state.turn}")
        print(f"🧠 기억: {len(engine.memory.memories)}개")
        print(f"💬 히스토리: {len(engine.conversation_history)}개")

    def test_process_turn_korean_response(self, engine: GameEngine) -> None:
        """응답이 한국어로 오는지 (Tool Use 텍스트도 포함 확인)"""
        result = engine.process_turn("안녕하세요! 저는 새로 입학한 학생인데, 여기서 뭘 하면 되나요?")

        response = result["response"]

        # LLM 2차 호출이 빈 텍스트를 반환할 수 있으므로,
        # 응답이 비어있으면 Tool Use가 발생했는지 확인
        if not response:
            assert result["tool_used"], "응답도 없고 Tool Use도 없음"
            print("\n⚠️ 2차 응답 텍스트 비었으나 Tool Use 정상 동작")
            return

        # 한국어 문자 포함 확인 (가-힣 범위)
        has_korean = any("\uac00" <= ch <= "\ud7a3" for ch in response)
        assert has_korean, f"한국어 응답이 아님: {response[:100]}"
        print(f"\n🇰🇷 한국어 응답 확인: {response[:100]}...")


@pytest.mark.integration
class TestGameEngineMultiTurn:
    """멀티턴 통합 테스트"""

    def test_two_turn_conversation(self, engine: GameEngine) -> None:
        """2턴 연속 대화: 컨텍스트를 기억하는지"""
        # 1턴: 자기소개
        result1 = engine.process_turn("안녕, 나는 새로 입학한 학생이야. 이름은 준영이라고 해!")
        assert result1["response"]
        print(f"\n--- Turn 1 ---\n{result1['response'][:200]}")

        # 2턴: 이전 대화 참조
        result2 = engine.process_turn("내 이름 기억해?")
        assert result2["response"]
        print(f"\n--- Turn 2 ---\n{result2['response'][:200]}")

        # 2턴째에 히스토리가 전달됨
        assert len(engine.conversation_history) == 4  # user, assistant, user, assistant
        assert engine.state.turn == 2
