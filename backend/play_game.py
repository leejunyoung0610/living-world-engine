#!/usr/bin/env python3
"""
Living World Engine - CLI Game Interface
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
    for npc in state.npcs:
        npc_id = npc.get("id")
        npc_name = npc.get("name")
        stats = relationships.get(npc_id, {})
        active_stats = [f"{stat}:{value}" for stat, value in stats.items() if value]
        if active_stats:
            print(f"  {npc_name}: {' '.join(active_stats)}")


def main():
    print_separator()
    print("🎮 Living World Engine - CLI Demo")
    print("Type 'quit' or 'q' to exit")
    print_separator()
    
    try:
        world_dir = Path(__file__).parent / "src/worlds/arcane_academy"
        engine = GameEngine()
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
