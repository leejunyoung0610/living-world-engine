# backend/tests/e2e/test_complete_playthrough.py
"""E2E Tests - Complete Game Playthrough"""
import pytest
import os
from backend.src.engine.game_loop import GameEngine


@pytest.mark.e2e
@pytest.mark.slow
class TestCompletePlaythrough:
    """완전한 게임 플레이 E2E 테스트"""
    
    @pytest.fixture
    def engine(self):
        """게임 엔진 초기화"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        
        engine = GameEngine()
        engine.initialize("backend/src/worlds/arcane_academy")
        return engine
    
    def test_10_turn_conversation(self, engine: GameEngine):
        """10턴 자연스러운 대화"""
        print("\n" + "="*60)
        print("10턴 대화 테스트 시작")
        print("="*60)
        
        scenario = [
            "안녕, 엘레나!",
            "같이 결투장 구경할래?",
            "너는 어떤 마법을 좋아해?",
            "가르쳐줄 수 있어?",
            "고마워!",
            "내일도 만날래?",
            "몇 시에?",
            "알았어!",
            "추천 책 있어?",
            "그럼 이만!"
        ]
        
        for i, user_input in enumerate(scenario, 1):
            print(f"\nTurn {i}:")
            result = engine.process_turn(user_input)
            
            # 검증
            assert result["response"], "응답 없음"
            assert "error" not in result, "에러 발생"
            
            print(f"  User: {user_input}")
            print(f"  NPC: {result['response'][:100]}...")
        
        # 최종 검증
        assert len(engine.memory.memories) >= 8, "기억 부족"
        print(f"\n✅ 완료! 총 기억: {len(engine.memory.memories)}")
    
    def test_loop_prevention(self, engine: GameEngine):
        """루프 감지 및 이벤트 주입"""
        print("\n" + "="*60)
        print("루프 방지 테스트")
        print("="*60)
        
        for i in range(10):
            result = engine.process_turn("안녕")
            severity = result.get("loop_severity", 0)
            
            print(f"Turn {i+1}: severity={severity}")
            
            if severity >= 7:
                assert result.get("events_triggered"), "이벤트 필요"
                print(f"  🎲 {result['events_triggered'][0]['name']}")
                break
        
        print("✅ 루프 방지 작동!")