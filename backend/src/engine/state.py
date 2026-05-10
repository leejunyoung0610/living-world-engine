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

from ..utils.logger import get_logger

logger = get_logger(__name__)


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

    @classmethod
    def load_from_file(cls, world_path: Path, characters_path: Path) -> WorldState:
        """두 JSON 파일에서 WorldState를 생성하여 반환

        Args:
            world_path: world.json 경로 (세계관 설정)
            characters_path: characters.json 경로 (플레이어 + NPC)

        Returns:
            초기화된 WorldState 인스턴스

        Raises:
            FileNotFoundError: 파일이 존재하지 않을 때 (파일명 포함 메시지)
            json.JSONDecodeError: JSON 파싱 실패 시
            ValueError: 필수 필드 누락 시 (누락 필드명 포함 메시지)
        """
        world_path = Path(world_path)
        characters_path = Path(characters_path)

        # ── 파일 존재 확인 ──
        if not world_path.exists():
            raise FileNotFoundError(f"세계관 파일을 찾을 수 없습니다: {world_path}")
        if not characters_path.exists():
            raise FileNotFoundError(f"캐릭터 파일을 찾을 수 없습니다: {characters_path}")

        # ── JSON 로드 ──
        with open(world_path, "r", encoding="utf-8") as f:
            world_data = json.load(f)

        with open(characters_path, "r", encoding="utf-8") as f:
            characters_data = json.load(f)

        return cls.load_from_dicts(world_data, characters_data, world_label=str(world_path))

    @classmethod
    def load_from_dicts(
        cls,
        world_data: dict[str, Any],
        characters_data: dict[str, Any],
        *,
        world_label: str = "world",
        characters_label: str = "characters",
    ) -> WorldState:
        """이미 파싱된 world / characters dict로 WorldState 생성 (UGC·API용)."""
        for field in ("id", "name"):
            if field not in world_data:
                raise ValueError(
                    f"{world_label}에 필수 필드 '{field}'가 누락되었습니다."
                )

        for field in ("npcs",):
            if field not in characters_data:
                raise ValueError(
                    f"{characters_label}에 필수 필드 '{field}'가 누락되었습니다."
                )

        state = cls()
        state.world = world_data
        raw_player = characters_data.get("player")
        if isinstance(raw_player, dict) and raw_player:
            state.player = raw_player
        else:
            # 템플릿 전용(npcs만) 또는 자리 표시; UGC 플레이는 API에서 player 합성 후 로드됨
            state.player = {"name": "플레이어", "class": "traveler", "stats": {}}
        if "stats" not in state.player:
            state.player["stats"] = {}
        elif state.player["stats"] is None:
            state.player["stats"] = {}
        elif not isinstance(state.player["stats"], dict):
            state.player["stats"] = {}
        state.npcs = characters_data["npcs"]
        state.quests = characters_data.get("quests", [])

        return state

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
        logger.info(f"Updating {npc_id} {stat} {change}")

        current = self.player["relationships"][npc_id].get(stat, 50)
        logger.info(f"Current {stat}: {current}")
        new_value = max(0, min(100, current + change))
        if new_value != current + change:
            logger.info(f"Clamped {stat} to {new_value} (requested {current + change})")
        self.player["relationships"][npc_id][stat] = new_value
        logger.info(f"{npc_id} {stat}: {current} -> {new_value} ({change})")
        return new_value

    # ── 자원 스탯·플래그 (이벤트 효과 적용용) ──
    #
    # 「감정·관계」 는 LLM 이 이야기 흐름에서 자연스럽게 update_relationship 으로 변동.
    # 이 두 메서드는 **자원 스탯**(hp, stress, focus 등)과 **플래그**(불리언/문자열 마커) 전용
    # 이벤트 효과에서만 호출한다.

    def update_player_stat(
        self,
        key: str,
        change: int,
        *,
        clamp: tuple[int, int] | None = None,
    ) -> tuple[int, int]:
        """``player.stats[key]`` 를 ``change`` 만큼 가감. ``clamp=(min,max)`` 면 범위 제한.

        Returns:
            (before, after) — 적용 전/후 정수값.
        """
        stats = self.player.get("stats")
        if not isinstance(stats, dict):
            stats = {}
            self.player["stats"] = stats
        before = int(stats.get(key, 0))
        target = before + int(change)
        if clamp is not None:
            lo, hi = clamp
            target = max(int(lo), min(int(hi), target))
        stats[key] = target
        return before, target

    def set_flag(self, key: str, value: Any) -> tuple[Any, Any]:
        """``player.flags[key]`` 를 ``value`` 로 설정. (before, after) 반환."""
        flags = self.player.get("flags")
        if not isinstance(flags, dict):
            flags = {}
            self.player["flags"] = flags
        before = flags.get(key)
        flags[key] = value
        return before, value

    def get_flag(self, key: str, default: Any = None) -> Any:
        flags = self.player.get("flags", {})
        if not isinstance(flags, dict):
            return default
        return flags.get(key, default)

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

    def to_save_dict(self) -> dict[str, Any]:
        """파일 저장과 동일한 구조의 dict (DB 스냅샷용)."""
        return {
            "world": deepcopy(self.world),
            "player": deepcopy(self.player),
            "npcs": deepcopy(self.npcs),
            "quests": deepcopy(self.quests),
            "turn": self.turn,
            "day": self.day,
            "memories": deepcopy(self.memories),
        }

    def restore_from_save_dict(self, data: dict[str, Any]) -> None:
        """`to_save_dict` / `save_to_file` 형식 dict로 상태 복원."""
        self.world = deepcopy(data.get("world", {}))
        self.player = deepcopy(data.get("player", {}))
        self.npcs = deepcopy(data.get("npcs", []))
        self.quests = deepcopy(data.get("quests", []))
        self.turn = int(data.get("turn", 0))
        self.day = int(data.get("day", 1))
        self.memories = deepcopy(data.get("memories", []))

    def save_to_file(self, path: Path) -> None:
        """현재 상태를 JSON 파일로 저장"""
        data = self.to_save_dict()
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
