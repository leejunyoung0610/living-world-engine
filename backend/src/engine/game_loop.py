"""
GameEngine - 메인 게임 루프

모든 엔진 컴포넌트를 연결하는 메인 루프입니다.

TODO: Week 2 Day 13-14에 구현 완성
"""

from __future__ import annotations

from typing import Any

from .state import WorldState
from .llm import ClaudeClient
from .validator import StateChangeValidator
from .loop_detector import LoopDetector
from .events import EventManager
from .prompt_optimizer import SystemPromptOptimizer
from ..utils.logger import get_logger
from ..utils.usage_tracker import UsageTracker
from ..utils.performance import PerformanceMonitor
from .long_term_memory import LongTermMemory

logger = get_logger(__name__)

class GameEngine:
    """메인 게임 엔진 - 한 턴의 전체 플로우를 관리"""

    def __init__(self) -> None:
        self.state = WorldState()
        self.memory = LongTermMemory(storage_path="data/memories.json")
        self.llm = ClaudeClient()
        self.validator = StateChangeValidator()
        self.loop_detector = LoopDetector()
        self.event_manager = EventManager()
        self.conversation_history: list[dict[str, Any]] = []
        self.usage_tracker = UsageTracker()
        self.prompt_optimizer = SystemPromptOptimizer()
        self.performance = PerformanceMonitor()

    def initialize(self, world_dir: str) -> None:
        """게임 초기화 - 세계관 디렉토리에서 world.json + characters.json + events.json 로드"""
        from pathlib import Path

        world_dir_path = Path(world_dir)
        self.state = WorldState.load_from_file(
            world_path=world_dir_path / "world.json",
            characters_path=world_dir_path / "characters.json",
        )
        self.validator.set_valid_characters(self.state.get_all_character_names())

        # 이벤트 로딩 (파일 있으면)
        events_path = world_dir_path / "events.json"
        if events_path.exists():
            self.event_manager.load_events_from_file(events_path)
            logger.info(f"이벤트 {len(self.event_manager.event_templates)}개 로딩 완료")

        logger.info(f"게임 초기화 완료: {world_dir}")

    def process_turn(self, user_input: str) -> dict[str, Any]:
        logger.info(f"=== Turn {self.state.turn + 1} ===")
        logger.info(f"Player: {user_input}")

        with self.performance.measure("total_turn"):
            with self.performance.measure("memory_search"):
                relevant_memories = self.memory.search(
                    query=user_input,
                    player_id=self.state.player.get("id", "default"),
                    min_importance=5,
                    limit=5,
                )

            with self.performance.measure("prompt_building"):
                system_prompt = self._build_system_prompt(relevant_memories)

            with self.performance.measure("llm_call"):
                llm_result = self.llm.process_turn(
                    user_input=user_input,
                    system_prompt=system_prompt,
                    conversation_history=self.conversation_history.copy(),
                )

            with self.performance.measure("usage_logging"):
                turn_cost = self.usage_tracker.log_call(
                    input_tokens=llm_result.get("input_tokens", 0),
                    output_tokens=llm_result.get("output_tokens", 0),
                    cache_creation_tokens=llm_result.get("cache_creation_tokens", 0),
                    cache_read_tokens=llm_result.get("cache_read_tokens", 0),
                )
                logger.debug(f"Turn cost: ${turn_cost:.6f}")

            with self.performance.measure("state_update"):
                state_changes = llm_result.get("state_changes", {})
                if state_changes:
                    state_changes = self.validator.validate(state_changes)

                applied = self.state.apply_changes(state_changes)
                self.state.advance_turn()

                for mem in state_changes.get("new_memories", []):
                    self.memory.add_memory(
                        content=mem["content"],
                        emotion=mem.get("emotion", "neutral"),
                        importance=mem.get("importance", 5),
                        player_id=self.state.player.get("id", "default"),
                    )

            snapshot = self.state.snapshot()
            response_text = llm_result.get("response", "")

            with self.performance.measure("loop_detection"):
                loop_result = self.loop_detector.detect_loop(snapshot, response_text)

            events_triggered: list[dict[str, Any]] = []
            with self.performance.measure("event_system"):
                triggered_events = self.event_manager.check_events(snapshot)
                for event in triggered_events:
                    self.event_manager.trigger_event(event["id"])
                    events_triggered.append({
                        "event_id": event["id"],
                        "description": event.get("description", ""),
                        "narrative_hint": event.get("narrative_hint", ""),
                    })
                    logger.info(f"🎲 이벤트 발생: {event.get('description', event['id'])}")

                if loop_result["detected"] and loop_result.get("severity", 0) >= 7:
                    surprise = {
                        "event_id": f"surprise_{self.state.turn}",
                        "description": "예상치 못한 돌발 상황이 발생합니다",
                        "narrative_hint": "갑자기 주변이 소란스러워진다...",
                    }
                    events_triggered.append(surprise)
                    logger.info(
                        f"⚠️ 루프 감지 (severity {loop_result['severity']}) → 강제 이벤트 주입"
                    )
                self.event_manager.tick_cooldowns()

            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            if len(self.conversation_history) > 40:
                self.conversation_history = self.conversation_history[-40:]

        result = {
            "turn": self.state.turn,
            "day": self.state.day,
            "response": response_text,
            "state_changes": applied,
            "tool_used": llm_result.get("tool_used", False),
            "loop_detected": loop_result["detected"],
            "loop_severity": loop_result.get("severity", 0),
            "events_triggered": events_triggered,
            "turn_cost": round(turn_cost, 6),
            "input_tokens": llm_result.get("input_tokens", 0),
            "output_tokens": llm_result.get("output_tokens", 0),
        }

        logger.info(f"NPC: {response_text[:100]}...")
        logger.info(
            f"Tool Used: {result['tool_used']}, "
            f"Loop: {result['loop_detected']} (severity {result['loop_severity']})"
        )

        return result

    def _build_system_prompt(self, relevant_memories: list[dict[str, Any]]) -> str:
        prompt = self.prompt_optimizer.build_optimized_prompt(
            world=self.state.world,
            player=self.state.player,
            active_location=self.state.player.get("location", "Unknown"),
            npcs=self.state.npcs,
            memories=relevant_memories,
        )

        logger.debug(f"Optimized prompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)")
        return prompt
    def _format_npc_profiles(self, snapshot: dict[str, Any]) -> str:
        """전체 NPC 데이터에서 상세 프로필 텍스트 생성"""
        profiles: list[str] = []
        relationships = self.state.player.get("relationships", {})

        for npc in self.state.npcs:
            npc_id = npc["id"]
            name = npc["name"]
            role = npc.get("role", "")
            location = npc.get("location", "")

            # 페르소나
            persona = npc.get("persona", {})
            traits = ", ".join(persona.get("traits", []))
            drive = persona.get("drive", "")
            taboos = persona.get("taboos", [])
            taboo_text = ", ".join(taboos) if taboos else "없음"

            # 스킬
            skills = npc.get("skills", [])
            skills_text = ", ".join(skills) if skills else "없음"

            # 말투
            style = npc.get("speech_style", {})
            formality_map = {
                "polite": "존댓말",
                "casual": "반말",
                "stiff": "딱딱한 공식체",
            }
            formality = formality_map.get(style.get("formality", ""), style.get("formality", ""))
            length_map = {
                "short": "짧은 문장",
                "medium": "보통 문장",
                "long": "긴 문장",
            }
            sentence_len = length_map.get(
                style.get("sentence_length", ""), style.get("sentence_length", "")
            )
            mood_map = {
                "mentor": "멘토처럼 차분",
                "tsundere": "츤데레 (까칠하지만 속은 따뜻)",
                "playful": "장난스럽고 여유",
                "shy": "소심하고 수줍음",
                "stern": "엄격하고 단호",
                "arrogant": "거만하고 비웃는 듯",
            }
            default_mood = mood_map.get(
                style.get("default_mood", ""), style.get("default_mood", "")
            )
            sig_phrases = style.get("signature_phrases", [])
            sig_text = ", ".join(f'"{p}"' for p in sig_phrases) if sig_phrases else ""

            # 관계 수치
            rel = relationships.get(npc_id, {})
            aff = rel.get("affection", 50)
            trust = rel.get("trust", 50)

            profile = f"""### {name} ({role})
- 위치: {location}
- 성격: {traits}
- 동기: {drive} | 금기: {taboo_text}
- 스킬: {skills_text}
- 말투: {formality}, {sentence_len}, {default_mood}
  - 특징적 대사: {sig_text}
  - 화나면: {style.get('when_angry', '?')}
  - 호감 높으면: {style.get('when_warm', '?')}
- 플레이어 관계: 호감 {aff}/100, 신뢰 {trust}/100"""

            profiles.append(profile)

        return "\n\n".join(profiles)

    def _format_memories(self, relevant_memories: list[dict[str, Any]]) -> str:
        """기억 목록을 포맷팅"""
        if not relevant_memories:
            return ""

        lines: list[str] = []
        for mem in relevant_memories:
            emotion = mem.get("emotion", "neutral")
            importance = mem.get("importance", 5)
            content = mem["content"]
            lines.append(f"- [{emotion}, 중요도 {importance}] {content}")
        return "\n".join(lines)

    def get_state(self) -> dict[str, Any]:
        """현재 게임 상태 반환"""
        return self.state.snapshot()

    def save(self, save_name: str) -> str:
        """게임 저장"""
        from ..utils.config import SAVES_DIR

        save_path = SAVES_DIR / f"{save_name}.json"
        self.state.save_to_file(save_path)
        return str(save_path)
