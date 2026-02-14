#!/usr/bin/env python3
"""실제 세계관 데이터 로딩 검증"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.src.engine.state import WorldState


def main():
    print("🌍 Arcane Academy 세계관 로딩 테스트")
    print("=" * 50)

    try:
        world = WorldState.load_from_file(
            Path("backend/src/worlds/arcane_academy/world.json"),
            Path("backend/src/worlds/arcane_academy/characters.json"),
        )

        print("✅ 로딩 성공!\n")

        # 세계관 정보
        print(f"🏰 세계: {world.world['id']}")
        print(f"📍 이름: {world.world['name']}")
        print(f"📖 설명: {world.world['description']}")
        print(f"⏰ 시간: {world.world['time']}")
        print(f"🗺️  지역: {', '.join(world.world.get('regions', []))}")
        print()

        # 세계 변수
        wv = world.world.get("world_variables", {})
        print("📊 세계 변수:")
        for key, val in wv.items():
            print(f"   {key}: {val}")
        print()

        # 플레이어 정보
        player = world.player
        print(f"👤 플레이어:")
        print(f"   이름: {player['name']}")
        print(f"   클래스: {player['class']}")
        stats = player.get("stats", {})
        print(f"   스탯: HP={stats.get('hp')} | MANA={stats.get('mana')} | FOCUS={stats.get('focus')}")
        print()

        # NPC 목록
        npcs = world.npcs
        print(f"👥 NPC 수: {len(npcs)}명\n")

        for npc in npcs:
            print(f"   📛 {npc['name']} ({npc['id']})")
            print(f"      역할: {npc['role']}")
            print(f"      위치: {npc['location']}")
            if "skills" in npc and npc["skills"]:
                print(f"      스킬: {', '.join(npc['skills'])}")
            persona = npc.get("persona", {})
            if persona:
                print(f"      성격: {', '.join(persona.get('traits', []))}")
            print()

        # 관계 확인
        rels = player.get("relationships", {})
        if rels:
            print("💕 초기 관계:")
            for npc_id, stats in rels.items():
                npc = world.get_npc(npc_id)
                name = npc["name"] if npc else npc_id
                print(f"   {name}: {stats}")
            print()

        # 상태 확인
        print(f"🔄 턴: {world.turn} | 일차: {world.day}")
        print(f"🧠 기억: {len(world.memories)}개")

        print()
        print("=" * 50)
        print("🎉 모든 데이터 정상 로딩됨!")
        return 0

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
