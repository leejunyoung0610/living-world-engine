"""
WorldState - 게임 세계 상태 관리

모든 게임 상태를 관리하는 핵심 클래스.
캐릭터 관계, 플레이어 스탯, 세계 변수, 퀘스트 등을 추적합니다.

TODO: Week 1 Day 3-4에 구현
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class WorldState:
    """게임 세계의 전체 상태를 관리하는 클래스"""

    def __init__(self) -> None:
        self.world: dict[str, Any] = {}
        self.player: dict[str, Any] = {}
        self.npcs: list[dict[str, Any]] = []
        self.quests: list[dict[str, Any]] = []
        self.turn: int = 0
        self.day: int = 1
        self.memories: list[dict[str, Any]] = []

    def load_from_file(self, path: Path) -> None:
        """JSON 파일에서 초기 상태 로드"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.world = data.get("world", {})
        self.player = data.get("player", {})
        self.npcs = data.get("npcs", [])
        self.quests = data.get("quests", [])

    def get_npc(self, npc_id: str) -> dict[str, Any] | None:
        """NPC ID로 NPC 데이터 조회"""
        for npc in self.npcs:
            if npc.get("id") == npc_id:
                return npc
        return None

    def get_npc_by_name(self, name: str) -> dict[str, Any] | None:
        """NPC 이름으로 NPC 데이터 조회"""
        for npc in self.npcs:
            if npc.get("name") == name:
                return npc
        return None

    def get_all_character_names(self) -> list[str]:
        """모든 NPC 이름 목록 반환"""
        return [npc["name"] for npc in self.npcs if "name" in npc]

    def get_relationship(self, npc_id: str, stat: str) -> int:
        """특정 NPC와의 관계 수치 조회"""
        relationships = self.player.get("relationships", {})
        npc_rel = relationships.get(npc_id, {})
        return npc_rel.get(stat, 50)  # 기본값 50

    def update_relationship(self, npc_id: str, stat: str, change: int) -> int:
        """관계 수치 업데이트 (0-100 범위 제한)"""
        if "relationships" not in self.player:
            self.player["relationships"] = {}
        if npc_id not in self.player["relationships"]:
            self.player["relationships"][npc_id] = {}

        current = self.player["relationships"][npc_id].get(stat, 50)
        new_value = max(0, min(100, current + change))
        self.player["relationships"][npc_id][stat] = new_value
        return new_value

    def apply_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        """검증된 상태 변경을 적용하고 적용된 변경 내역을 반환"""
        applied: dict[str, Any] = {"relationship_changes": [], "memories_added": []}

        # 관계 변경 적용
        for rc in changes.get("relationship_changes", []):
            character = rc.get("character", "")
            stat = rc.get("stat", "")
            change = rc.get("change", 0)

            # NPC 존재 확인
            npc = self.get_npc_by_name(character) or self.get_npc(character)
            if npc:
                npc_id = npc["id"]
                new_val = self.update_relationship(npc_id, stat, change)
                applied["relationship_changes"].append(
                    {"character": character, "stat": stat, "change": change, "new_value": new_val}
                )

        # 새 기억 추가
        for mem in changes.get("new_memories", []):
            memory = {
                "content": mem.get("content", ""),
                "emotion": mem.get("emotion", "neutral"),
                "importance": mem.get("importance", 5),
                "turn": self.turn,
                "day": self.day,
            }
            self.memories.append(memory)
            applied["memories_added"].append(memory)

        return applied

    def advance_turn(self) -> None:
        """턴 진행"""
        self.turn += 1
        # 매 5턴마다 하루 경과
        if self.turn % 5 == 0:
            self.day += 1

    def save_to_file(self, path: Path) -> None:
        """현재 상태를 JSON 파일로 저장"""
        data = {
            "world": self.world,
            "player": self.player,
            "npcs": self.npcs,
            "quests": self.quests,
            "turn": self.turn,
            "day": self.day,
            "memories": self.memories,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def snapshot(self) -> dict[str, Any]:
        """현재 상태의 스냅샷 (LLM 컨텍스트용)"""
        return {
            "world": deepcopy(self.world),
            "player": {
                "name": self.player.get("name", "Unknown"),
                "class": self.player.get("class", "Unknown"),
                "stats": self.player.get("stats", {}),
                "flags": self.player.get("flags", {}),
                "relationships": self.player.get("relationships", {}),
            },
            "npcs": [
                {
                    "id": npc["id"],
                    "name": npc["name"],
                    "role": npc.get("role", ""),
                    "location": npc.get("location", ""),
                }
                for npc in self.npcs
            ],
            "turn": self.turn,
            "day": self.day,
        }
