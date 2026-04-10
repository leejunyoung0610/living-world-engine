"""
GameEngine - 메인 게임 루프

모든 엔진 컴포넌트를 연결하는 메인 루프입니다.

TODO: Week 2 Day 13-14에 구현 완성
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import WorldState
from .llm import ClaudeClient
from .validator import StateChangeValidator
from .loop_detector import LoopDetector
from .events import EventManager
from .prompt_optimizer import SystemPromptOptimizer
from ..utils.config import get_settings
from ..utils.logger import get_logger
from ..utils.usage_tracker import UsageTracker
from ..utils.performance import PerformanceMonitor
from .long_term_memory import LongTermMemory
from .context_manager import ContextManager

logger = get_logger(__name__)


def _summarize_api_usage(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Anthropic Messages 응답 `usage` 필드 기준 합산 (추정이 아닌 API 집계)."""
    by_call: list[dict[str, Any]] = []
    for i, s in enumerate(segments, start=1):
        by_call.append(
            {
                "call_index": i,
                "input_tokens": int(s.get("input_tokens", 0)),
                "output_tokens": int(s.get("output_tokens", 0)),
                "cache_creation_input_tokens": int(
                    s.get("cache_creation_tokens", 0)
                ),
                "cache_read_input_tokens": int(s.get("cache_read_tokens", 0)),
            }
        )
    totals = {
        "input_tokens": sum(x["input_tokens"] for x in by_call),
        "output_tokens": sum(x["output_tokens"] for x in by_call),
        "cache_creation_input_tokens": sum(
            x["cache_creation_input_tokens"] for x in by_call
        ),
        "cache_read_input_tokens": sum(
            x["cache_read_input_tokens"] for x in by_call
        ),
    }
    return {"by_call": by_call, "totals": totals}


class GameEngine:
    """메인 게임 엔진 - 한 턴의 전체 플로우를 관리"""

    def __init__(self) -> None:
        self.state = WorldState()
        self.memory = LongTermMemory()
        self.llm = ClaudeClient()
        self.validator = StateChangeValidator()
        self.loop_detector = LoopDetector()
        self.event_manager = EventManager()
        self.conversation_history: list[dict[str, Any]] = []
        self.usage_tracker = UsageTracker(llm_model=self.llm.model)
        self.prompt_optimizer = SystemPromptOptimizer()
        self.performance = PerformanceMonitor()
        self.context_manager = ContextManager()
        self.cache_reset_flag = None  # Cache 강제 초기화용

    def initialize(self, world_dir: str) -> None:
        """게임 초기화 - 세계관 디렉토리에서 world.json + characters.json + events.json 로드"""
        from pathlib import Path

        world_dir_path = Path(world_dir)
        self.state = WorldState.load_from_file(
            world_path=world_dir_path / "world.json",
            characters_path=world_dir_path / "characters.json",
        )
        self.validator.set_valid_characters(self.state.get_all_character_names())

        # NPC 이름 추출 (세계관 독립적)
        npc_names = [npc.get("name") for npc in self.state.npcs if npc.get("name")]
        
        # ContextManager에 NPC 이름 설정
        self.context_manager.set_npc_names(npc_names)
        
        # LongTermMemory에 NPC 이름 설정
        self.memory.set_npc_names(npc_names)

        # 이벤트 로딩 (파일 있으면)
        events_path = world_dir_path / "events.json"
        if events_path.exists():
            self.event_manager.load_events_from_file(events_path)
            logger.info(f"이벤트 {len(self.event_manager.event_templates)}개 로딩 완료")

        logger.info("게임 초기화 완료: %s", world_dir)
        logger.info("🤖 LLM: %s (max_tokens=%s)", self.llm.model, self.llm.max_tokens)

    def initialize_from_dicts(
        self,
        world_data: dict[str, Any],
        characters_data: dict[str, Any],
        events_data: dict[str, Any] | list[dict[str, Any]] | None = None,
        *,
        memory_storage_path: Path | str | None = None,
    ) -> None:
        """DB·UGC JSON으로 초기화. `memory_storage_path`가 있으면 세션별 장기기억 파일 사용."""
        self.state = WorldState.load_from_dicts(world_data, characters_data)
        self.validator.set_valid_characters(self.state.get_all_character_names())

        npc_names = [npc.get("name") for npc in self.state.npcs if npc.get("name")]
        self.context_manager.set_npc_names(npc_names)

        if memory_storage_path is not None:
            self.memory = LongTermMemory(storage_path=Path(memory_storage_path))
        self.memory.set_npc_names(npc_names)

        self.event_manager = EventManager()
        if events_data:
            if isinstance(events_data, list):
                self.event_manager.load_events(events_data)
            elif isinstance(events_data, dict) and "events" in events_data:
                ev = events_data["events"]
                if isinstance(ev, list):
                    self.event_manager.load_events(ev)

        self.conversation_history = []
        logger.info("게임 초기화 완료 (dict 소스), memory=%s", memory_storage_path or "default")

    def process_turn(self, user_input: str) -> dict[str, Any]:
        logger.info(f"=== Turn {self.state.turn + 1} ===")
        logger.info(f"Player: {user_input}")

        with self.performance.measure("total_turn"):
            with self.performance.measure("memory_search"):
                # Layer 3: 장기 중요 기억 (전체 범위, importance >= 7)
                relevant_memories = self.memory.search(
                    query=user_input,
                    player_id=self.state.player.get("id", "default"),
                    min_importance=7,  # 5 → 7로 상향 (중요 사건만)
                    limit=10,          # 5 → 10으로 증가
                )
                
                # Layer 3: 요약만 INFO, 미리보기는 DEBUG (터미널 스팸 방지)
                logger.info(f"🧠 Layer 3 (LongTermMemory): {len(relevant_memories)}개 검색")
                if relevant_memories:
                    for mem in relevant_memories[:3]:
                        logger.debug(
                            "   L3 [%s] %s...",
                            mem.get("importance", "?"),
                            (mem.get("content") or "")[:60],
                        )

            with self.performance.measure("prompt_building"):
                system_blocks = self._build_system_blocks(relevant_memories)

            with self.performance.measure("llm_call"):
                full_history = self.conversation_history.copy()
                full_history.append({"role": "user", "content": user_input})
                
                # Layer 1 + Layer 2: 대화 히스토리 최적화
                optimized_history = self.context_manager.build_context(
                    user_input,
                    full_history,
                    max_tokens=ContextManager.MAX_CONTEXT_TOKENS,
                )
                llm_result = self.llm.process_turn(
                    user_input=user_input,
                    system_prompt=system_blocks,
                    conversation_history=optimized_history,
                    enable_single_pass=get_settings().enable_single_pass,
                )

            _calls = int(llm_result.get("llm_api_calls", 1))
            logger.info("📡 LLM API 호출 수: %s회", _calls)
            if _calls == 1 and llm_result.get("tool_used"):
                logger.info("✅ Single-Pass (1회 호출, 툴+대사 동시)")
            elif _calls == 2:
                logger.info("⚠️ Tool Use → 2차 호출 (Fallback)")

            with self.performance.measure("usage_logging"):
                segments = llm_result.get("usage_segments")
                if not segments:
                    segments = [
                        {
                            "input_tokens": llm_result.get("input_tokens", 0),
                            "output_tokens": llm_result.get("output_tokens", 0),
                            "cache_creation_tokens": llm_result.get(
                                "cache_creation_tokens", 0
                            ),
                            "cache_read_tokens": llm_result.get("cache_read_tokens", 0),
                        }
                    ]
                turn_cost = self.usage_tracker.log_turn_anthropic(segments)
                api_usage = _summarize_api_usage(segments)
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
                self.memory.maybe_compact_if_oversized()

            snapshot = self.state.snapshot()
            response_text = llm_result.get("response", "")

            # Loop Detection 비활성화 (Week 3 재평가 예정)
            # with self.performance.measure("loop_detection"):
            #     loop_result = self.loop_detector.detect_loop(snapshot, response_text)
            loop_result = {"detected": False, "severity": 0}  # 비활성화

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

                # Loop Detection 비활성화
                # if loop_result["detected"] and loop_result.get("severity", 0) >= 7:
                #     surprise = {
                #         "event_id": f"surprise_{self.state.turn}",
                #         "description": "예상치 못한 돌발 상황이 발생합니다",
                #         "narrative_hint": "갑자기 주변이 소란스러워진다...",
                #     }
                #     events_triggered.append(surprise)
                #     logger.info(
                #         f"⚠️ 루프 감지 (severity {loop_result['severity']}) → 강제 이벤트 주입"
                #     )
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
            "input_tokens_first": llm_result.get("input_tokens_first", 0),
            "input_tokens_second": llm_result.get("input_tokens_second", 0),
            "output_tokens": llm_result.get("output_tokens", 0),
            "cache_creation_tokens": llm_result.get("cache_creation_tokens", 0),
            "cache_read_tokens": llm_result.get("cache_read_tokens", 0),
            # Anthropic Messages 응답 usage 기준 (호출별 + 합계). 추정 토큰 아님.
            "api_usage": api_usage,
            "llm_api_calls": int(llm_result.get("llm_api_calls", 1)),
        }

        _tot = api_usage["totals"]
        logger.info(
            "📡 API usage: input=%s output=%s cache_write=%s cache_read=%s | "
            "추정 비용(단가표)=$%.6f",
            _tot["input_tokens"],
            _tot["output_tokens"],
            _tot["cache_creation_input_tokens"],
            _tot["cache_read_input_tokens"],
            turn_cost,
        )
        logger.info(f"NPC: {response_text[:100]}...")
        logger.info(
            f"Tool Used: {result['tool_used']}, "
            f"Loop: {result['loop_detected']} (severity {result['loop_severity']})"
        )

        return result

    def _build_system_blocks(
        self, relevant_memories: list[dict[str, Any]]
    ) -> tuple[str, str]:
        """(static, dynamic) 시스템 블록 — static만 Anthropic 프롬프트 캐시 대상."""
        static, dynamic = self.prompt_optimizer.build_system_blocks(
            world=self.state.world,
            player=self.state.player,
            active_location=self.state.player.get("location", "Unknown"),
            npcs=self.state.npcs,
            memories=relevant_memories,
            cache_reset_flag=self.cache_reset_flag,
        )
        total = len(static) + len(dynamic)
        logger.debug(
            "System blocks: static=%s dynamic=%s total=%s chars (~%s tokens)",
            len(static),
            len(dynamic),
            total,
            total // 4,
        )
        return static, dynamic

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

    def print_performance_report(self) -> None:
        """성능 모니터링 리포트 출력"""
        self.performance.print_report()
