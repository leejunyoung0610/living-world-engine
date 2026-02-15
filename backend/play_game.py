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
    state = engine.state
    
    print(f"🌍 World: {state.world.get('name', 'Unknown')}")
    print(f"👤 Player: {state.player.get('name', 'Unknown')}")
    print(f"🔄 Turn: {state.turn}")
    print(f"📍 Location: {state.player.get('location', 'Unknown')}")
    
    # 관계도 표시
    print("\n💫 Relationships:")
    relationships = state.player.get("relationships", {})
    stat_order = [
        ("affection", "😊"),
        ("trust", "🤝"),
        ("respect", "⭐"),
        ("fear", "😱"),
        ("loyalty", "💎"),
        ("romance", "💕"),
    ]
    shown = False
    player_stats = state.player.get("stats", {})
    for npc in state.npcs:
        npc_id = npc.get("id")
        rel_data = relationships.get(npc_id, {})
        entries = []
        for stat, emoji in stat_order:
            value = rel_data.get(stat, player_stats.get(stat, 0))
            if value > 0:
                entries.append(f"{emoji}{value}")
        if entries:
            shown = True
            print(f"  {npc.get('name')}: {' '.join(entries)}")

    if not shown:
        print("  (아직 관계 정보 없음)")
    
    # 루프 경고
 #   if hasattr(engine, 'loop_detector'):
  #      severity = engine.loop_detector.calculate_severity()
   #     if severity >= 7:
    #        print(f"\n⚠️  Loop Warning: Severity {severity}/10")
     #   elif severity >= 5:
      #      print(f"ℹ️  Stagnation detected: {severity}/10")


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