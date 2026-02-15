#!/usr/bin/env python3
"""
Living World Engine - CLI Game Interface
Day 5 - Manual playthrough script
"""

import sys
from pathlib import Path
from src.engine.game_loop import GameEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


def print_separator():
    print("\n" + "="*60 + "\n")


def print_game_state(engine: GameEngine):
    """현재 게임 상태 출력"""
    state = engine.world_state
    
    print(f"🌍 World: {state.world_name}")
    print(f"👤 Player: {state.player_name}")
    print(f"🔄 Turn: {state.turn_count}")
    print(f"📍 Location: {state.current_location}")
    
    # 관계도 표시
    if state.relationships:
        print("\n💫 Relationships:")
        for char, value in state.relationships.items():
            emoji = "❤️" if value > 50 else "😊" if value > 0 else "😐"
            print(f"  {emoji} {char}: {value}")
    
    # 루프 경고
    if hasattr(engine, 'loop_detector'):
        severity = engine.loop_detector.calculate_severity()
        if severity >= 7:
            print(f"\n⚠️  Loop Warning: Severity {severity}/10")
        elif severity >= 5:
            print(f"ℹ️  Stagnation detected: {severity}/10")


def main():
    print_separator()
    print("🎮 Living World Engine - CLI Demo")
    print("Type 'quit' or 'q' to exit")
    print_separator()
    
    # 게임 초기화
    try:
        world_dir = Path(__file__).parent / "src/worlds/arcane_academy"
        engine = GameEngine()
        engine.initialize(str(world_dir))
        logger.info("Game engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize game: {e}")
        print(f"❌ Error: {e}")
        return 1
    
    # 초기 상태 표시
    print_game_state(engine)
    print_separator()
    
    # 게임 루프
    while True:
        try:
            # 유저 입력
            user_input = input("You: ").strip()
            
            # 종료 명령
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Game ended. Goodbye!")
                break
            
            # 빈 입력 무시
            if not user_input:
                continue
            
            # 게임 턴 실행
            print("\n🤔 Processing...\n")
            result = engine.process_turn(user_input)
            response = result["response"]
            
            # 응답 출력
            print(f"🎭 {response}")
            print_separator()
            
            # 상태 업데이트 표시
            print_game_state(engine)
            print_separator()
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Exiting...")
            break
        except Exception as e:
            logger.error(f"Turn error: {e}", exc_info=True)
            print(f"\n❌ Error during turn: {e}")
            print("Game continues...\n")
    
    # 최종 상태 저장 (선택사항)
    try:
        save_path = Path(__file__).parent / "saves" / "last_session.json"
        save_path.parent.mkdir(exist_ok=True)
        # TODO: engine.save_state(save_path) 구현 시 활성화
        logger.info("Session ended")
    except Exception as e:
        logger.warning(f"Failed to save state: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())