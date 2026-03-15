#!/usr/bin/env python3
"""
Living World Engine - CLI Game Interface
"""

import argparse
import sys
from pathlib import Path

from src.engine.game_loop import GameEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Living World Engine CLI")
    parser.add_argument(
        "--world",
        default="campus",
        help="로드할 world 디렉토리 이름 (기본: campus)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="완전한 게임 초기화 (memories.json 삭제 + 안내)",
    )
    parser.add_argument(
        "--force-cache-reset",
        action="store_true",
        help="Prompt Cache 강제 초기화 (System Prompt에 타임스탬프 추가)",
    )
    return parser.parse_args()


def print_separator():
    print("\n" + "="*60 + "\n")


def print_game_state(engine: GameEngine):
    """현재 게임 상태 출력"""
    state = engine.state

    print(f"🌍 World: {state.world.get('name', 'Unknown')}")
    print(f"👤 Player: {state.player.get('name', 'Unknown')}")
    print(f"🔄 Turn: {state.turn}")
    print(f"📍 Location: {state.player.get('location', 'Unknown')}")

    print("\n💫 Relationships:")
    relationships = state.player.get("relationships", {})
    for npc in state.npcs:
        npc_id = npc.get("id")
        npc_name = npc.get("name")
        stats = relationships.get(npc_id, {})
        active_stats = [f"{stat}:{value}" for stat, value in stats.items() if value]
        if active_stats:
            print(f"  {npc_name}: {' '.join(active_stats)}")


def main():
    args = parse_args()
    print_separator()
    print("🎮 Living World Engine - CLI Demo")
    print("Type 'quit' or 'q' to exit")
    print_separator()

    # --reset 옵션 처리: 완전한 게임 초기화
    if args.reset:
        print("🗑️  게임 초기화 중...")
        
        # 1. LongTermMemory 초기화
        memory_path = Path(__file__).parent / "data" / "memories.json"
        if memory_path.exists():
            memory_path.unlink()
            print("   ✅ 장기 기억 삭제: memories.json")
            logger.info(f"Memory reset: {memory_path} deleted")
        
        # 2. 대화 히스토리는 자동으로 새로 시작 (메모리 초기화)
        print("   ✅ 대화 히스토리 초기화")
        
        # 3. Prompt Cache 안내
        print("\n💡 Prompt Cache 초기화 방법:")
        print("   • Option 1: 5분 대기 (자동 만료)")
        print("   • Option 2: 다른 world 선택 (--world arcane_academy)")
        print("   • Option 3: System Prompt 수정 시 자동 무효화")
        print("\n🎮 완전히 새로운 게임으로 시작합니다!")
        logger.info(f"Full game reset initiated for world: {args.world}")
        print_separator()

    world_dir = Path(__file__).parent / "src/worlds" / args.world
    if not world_dir.exists():
        logger.error(f"World directory {world_dir} not found")
        print(f"❌ World '{args.world}' 폴더를 찾을 수 없습니다.")
        return 1

    engine = GameEngine()
    
    # Cache 강제 초기화 옵션 전달
    if args.force_cache_reset:
        import time
        cache_reset_flag = f"_reset_{int(time.time())}"
        engine.cache_reset_flag = cache_reset_flag
        print("🔄 Prompt Cache 강제 초기화: System Prompt 변경됨")
        logger.info(f"Force cache reset: {cache_reset_flag}")
    
    try:
        engine.initialize(str(world_dir))
        logger.info("Game engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize game: {e}")
        print(f"❌ Error: {e}")
        return 1

    print_game_state(engine)
    print_separator()

    try:
        while True:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Game ended. Goodbye!")
                break

            if not user_input:
                continue

            print("\n🤔 Processing...\n")
            result = engine.process_turn(user_input)
            response = result["response"]

            print(f"🎭 {response}")
            print(f"\n💰 Turn Cost: ${result['turn_cost']:.6f}")
            print(f"   Input: {result['input_tokens']:,} tokens | "
                  f"Output: {result['output_tokens']:,} tokens")
            stats = engine.usage_tracker.get_stats()
            print(f"   Total Spent: ${stats['total_cost']:.6f}")

            print_separator()
            print_game_state(engine)
            print_separator()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Exiting...")
    except Exception as e:
        logger.error(f"Turn error: {e}", exc_info=True)
        print(f"\n❌ Error during turn: {e}")
        print("Game continues...\n")
    finally:
        print("\n")
        engine.usage_tracker.print_summary()
        engine.print_performance_report()
        logger.info("Session ended")

    return 0


if __name__ == "__main__":
    sys.exit(main())
