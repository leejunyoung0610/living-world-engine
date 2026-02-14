"""
GameEngine - 메인 게임 루프

모든 엔진 컴포넌트를 연결하는 메인 루프입니다.

TODO: Week 2 Day 13-14에 구현 완성
"""

from __future__ import annotations

from typing import Any

from backend.src.engine.state import WorldState
from backend.src.engine.memory import KeywordMemorySearch
from backend.src.engine.llm import ClaudeClient
from backend.src.engine.validator import StateChangeValidator
from backend.src.engine.loop_detector import LoopDetector
from backend.src.engine.events import EventManager
from backend.src.utils.logger import logger


class GameEngine:
    """메인 게임 엔진 - 한 턴의 전체 플로우를 관리"""

    def __init__(self) -> None:
        self.state = WorldState()
        self.memory = KeywordMemorySearch()
        self.llm = ClaudeClient()
        self.validator = StateChangeValidator()
        self.loop_detector = LoopDetector()
        self.event_manager = EventManager()
        self.conversation_history: list[dict[str, Any]] = []

    def initialize(self, world_path: str) -> None:
        """게임 초기화 - 세계관 로드"""
        from pathlib import Path

        self.state.load_from_file(Path(world_path))
        self.validator.set_valid_characters(self.state.get_all_character_names())
        logger.info(f"게임 초기화 완료: {world_path}")

    def process_turn(self, user_input: str) -> dict[str, Any]:
        """
        한 턴 처리

        1. 관련 기억 검색
        2. 시스템 프롬프트 구성
        3. LLM 호출 (Tool Use)
        4. 상태 변경 검증
        5. 상태 적용
        6. 루프 감지
        7. 이벤트 체크
        8. 결과 반환
        """
        logger.info(f"=== Turn {self.state.turn + 1} ===")
        logger.info(f"Player: {user_input}")

        # 1. 관련 기억 검색
        relevant_memories = self.memory.search(user_input, top_k=5)

        # 2. 시스템 프롬프트 구성
        system_prompt = self._build_system_prompt(relevant_memories)

        # 3. LLM 호출
        llm_result = self.llm.process_turn(
            user_input=user_input,
            system_prompt=system_prompt,
            conversation_history=self.conversation_history.copy(),
        )

        # 4. 상태 변경 검증
        state_changes = llm_result.get("state_changes", {})
        if state_changes:
            state_changes = self.validator.validate(state_changes)

        # 5. 상태 적용
        applied = self.state.apply_changes(state_changes)
        self.state.advance_turn()

        # 새 기억을 메모리 시스템에 추가
        for mem in state_changes.get("new_memories", []):
            self.memory.add_memory(
                content=mem["content"],
                emotion=mem.get("emotion", "neutral"),
                importance=mem.get("importance", 5),
            )

        # 6. 루프 감지
        snapshot = self.state.snapshot()
        response_text = llm_result.get("response", "")
        is_loop = self.loop_detector.is_loop_detected(snapshot, response_text)

        # 7. 이벤트 체크
        events = self.event_manager.check_events(snapshot)
        self.event_manager.tick_cooldowns()

        # 8. 대화 히스토리 업데이트
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": response_text})

        # 히스토리 길이 제한 (최근 20턴)
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        result = {
            "turn": self.state.turn,
            "day": self.state.day,
            "response": response_text,
            "state_changes": applied,
            "tool_used": llm_result.get("tool_used", False),
            "loop_detected": is_loop,
            "events": events,
        }

        logger.info(f"NPC: {response_text[:100]}...")
        logger.info(f"Tool Used: {result['tool_used']}, Loop: {result['loop_detected']}")

        return result

    def _build_system_prompt(self, relevant_memories: list[dict[str, Any]]) -> str:
        """시스템 프롬프트 구성"""
        snapshot = self.state.snapshot()

        # 기억 포맷팅
        memory_text = ""
        if relevant_memories:
            memory_lines = []
            for mem in relevant_memories:
                memory_lines.append(f"- [{mem.get('emotion', 'neutral')}] {mem['content']}")
            memory_text = "\n".join(memory_lines)

        # NPC 정보 포맷팅
        npc_text = ""
        for npc in snapshot["npcs"]:
            rel = snapshot["player"]["relationships"].get(npc["id"], {})
            npc_text += (
                f"- {npc['name']} ({npc['role']}): "
                f"호감 {rel.get('affection', 50)}, "
                f"신뢰 {rel.get('trust', 50)}\n"
            )

        prompt = f"""너는 판타지 RPG 세계 "{snapshot['world'].get('id', 'unknown')}"의 NPC들을 연기하는 게임 마스터야.

## 세계 정보
- 시간: {snapshot['world'].get('time', '알 수 없음')}
- 현재 턴: {snapshot['turn']}, 일차: {snapshot['day']}

## 플레이어 정보
- 이름: {snapshot['player']['name']}
- 직업: {snapshot['player']['class']}
- 스탯: {snapshot['player'].get('stats', {})}

## NPC 관계
{npc_text}

## 관련 기억
{memory_text if memory_text else '(아직 기억 없음)'}

## 규칙
1. 플레이어의 행동에 자연스럽게 반응해라
2. 반드시 update_game_state 도구를 사용하여 상태 변경을 제안해라
3. 관계 변화는 한 턴에 -10 ~ +10 범위로 제한해라
4. 새로운 기억을 최소 1개 이상 생성해라
5. 한국어로 응답해라
6. 대사와 행동 묘사를 자연스럽게 섞어라
"""
        return prompt

    def get_state(self) -> dict[str, Any]:
        """현재 게임 상태 반환"""
        return self.state.snapshot()

    def save(self, save_name: str) -> str:
        """게임 저장"""
        from backend.src.utils.config import SAVES_DIR

        save_path = SAVES_DIR / f"{save_name}.json"
        self.state.save_to_file(save_path)
        return str(save_path)
