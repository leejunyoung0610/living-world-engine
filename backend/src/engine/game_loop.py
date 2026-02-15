"""
GameEngine - 메인 게임 루프

모든 엔진 컴포넌트를 연결하는 메인 루프입니다.

TODO: Week 2 Day 13-14에 구현 완성
"""

from __future__ import annotations

from typing import Any

from .state import WorldState
from .llm import ClaudeClient
from .memory import KeywordMemorySearch
from .validator import StateChangeValidator
from .loop_detector import LoopDetector
from .events import EventManager
from ..utils.logger import get_logger
from ..utils.usage_tracker import UsageTracker

logger = get_logger(__name__)

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
        self.usage_tracker = UsageTracker()

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

        # 사용량 기록
        turn_cost = self.usage_tracker.log_call(
            input_tokens=llm_result.get("input_tokens", 0),
            output_tokens=llm_result.get("output_tokens", 0),
        )
        logger.debug(f"Turn cost: ${turn_cost:.6f}")

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

        # 6. 루프 감지 (강화된 버전)
        snapshot = self.state.snapshot()
        response_text = llm_result.get("response", "")
        loop_result = self.loop_detector.detect_loop(snapshot, response_text)

        # 7. 이벤트 체크 + 발동
        triggered_events = self.event_manager.check_events(snapshot)
        events_triggered: list[dict[str, Any]] = []
        for event in triggered_events:
            self.event_manager.trigger_event(event["id"])
            events_triggered.append({
                "event_id": event["id"],
                "description": event.get("description", ""),
                "narrative_hint": event.get("narrative_hint", ""),
            })
            logger.info(f"🎲 이벤트 발생: {event.get('description', event['id'])}")

        # 7-1. 심각한 루프 → 강제 돌발 이벤트 주입
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
        """시스템 프롬프트 구성 — NPC 페르소나 + 응답 스타일 가이드 포함"""
        snapshot = self.state.snapshot()
        world = self.state.world
        player = self.state.player

        # ── NPC 프로필 (전체 데이터에서 구성) ──
        npc_profiles = self._format_npc_profiles(snapshot)

        # ── 기억 포맷팅 ──
        memory_text = self._format_memories(relevant_memories)

        logger.debug(f"NPC profiles length: {len(npc_profiles)} chars")
        logger.debug(f"Memory text length: {len(memory_text)} chars")

        # ── 플레이어 스탯 포맷팅 ──
        stats = player.get("stats", {})
        stats_text = f"HP {stats.get('hp', '?')}/{stats.get('max_hp', '?')}, 마나 {stats.get('mana', '?')}/{stats.get('max_mana', '?')}, 집중 {stats.get('focus', '?')}"

        prompt = f"""너는 "{world.get('name', '알 수 없는 세계')}"의 NPC들을 연기하는 게임 마스터(GM)다.
플레이어가 말을 걸거나 행동하면, 해당 장면의 NPC로서 반응한다.

## 응답 형식 (반드시 지켜라)
- **대화 중심**: NPC의 대사가 응답의 핵심. 긴 서술이나 풍경 묘사 금지.
- **행동은 괄호로 간결하게**: (미소를 짓는다), (고개를 돌린다), (한숨)
- **분량**: 2~4문장. 절대 소설처럼 길게 쓰지 마라.
- **RPG 소설체 금지**: "~했다", "~였다" 같은 3인칭 서술 금지. NPC 시점으로 직접 말해라.
- **한국어로 응답**
- **장면 설정 금지**: "**[장소명]**" 같은 장면 헤더를 쓰지 마라. 바로 NPC 대사로 시작해라.

좋은 예:
(결투장 벤치에 앉아 노트를 넘기다 고개를 든다) "어머, 신입생? 결투장까지 찾아오다니 대단하네요." (살짝 미소) "혹시 마법 전투에 관심 있어요?"

나쁜 예:
**[아케인 아카데미 결투장]** 따뜻한 햇살이 결투장을 비추고 있었다. 엘레나는 우아하게 앉아 노트를 보고 있었는데, 신입생이 다가오자 은발이 바람에 흔들리며...

## 현재 상황
- 세계: {world.get('name', '?')} — {world.get('description', '')}
- 시간: {world.get('time', '알 수 없음')}
- 턴: {snapshot['turn']}, 일차: {snapshot['day']}
- 배경: {', '.join(world.get('facts', [])[:2])}

## 플레이어 정보
- 이름: {player.get('name', 'Unknown')}
- 클래스: {player.get('class', 'Unknown')}
- 스탯: {stats_text}

## NPC 프로필
{npc_profiles}

## 관련 기억
{memory_text if memory_text else '(아직 공유된 기억 없음 — 첫 만남)'}

## 🚨 긴급 발견 (Day 6 실제 플레이)

### **실제 비용 데이터**
```
Turn 1: $0.030660 (8,060 in / 432 out)
Turn 2: $0.031674 (8,428 in / 426 out)

평균: $0.031/turn
입력 토큰: 8,244개 (예상의 5.4배!)
```

### **문제:**
- 입력 토큰이 8,000개 (예상 1,500개)
- 어디선가 6,500 tokens 추가 유입
- 원인 불명 (디버깅 필요)

### **즉시 할 일:**
1. 시스템 프롬프트 각 부분 토큰 수 측정
2. 병목 지점 파악
3. 긴급 최적화

### **목표:**
- 8,000 → 1,500 tokens (81% 절감)
- $0.031 → $0.010/turn (68% 절감)

```
## Tool Use 규칙 (매 턴 반드시 실행)
1. **반드시** update_game_state 도구를 호출해라. 예외 없음.
2. relationship_changes:
   - 변화량은 **-5 ~ +5** 범위로 자연스럽게
   - 사소한 인사 = ±1~2, 호의적 행동 = +3~5, 적대 행동 = -3~-5
3. new_memories:
   - 최소 1개 생성
   - 사소한 인사 = importance 2~3
   - 의미 있는 대화 = importance 4~6
   - 감정적 사건(갈등, 고백, 결투) = importance 7~9
4. 기억 content는 1문장으로 사실만 적어라 (감상 금지)

```

## 🎯 새 채팅 시작 멘트
"```

## 🔍 디버깅 진행 중 (추가 발견)

### **로그 분석:**
```
Turn 1:
- 시스템 프롬프트: 841 tokens ✅
- 실제 입력: 9,340 tokens 😱
- 차이: 8,499 tokens 미확인

Turn 2:
- 시스템 프롬프트: 854 tokens ✅  
- 실제 입력: 9,924 tokens 😱
- 차이: 9,070 tokens 미확인
```

### **의심되는 범인:**
**Tool Use 스키마!**

Claude API에 매번 전달되는 `tools` 정의가 엄청 클 가능성.
- Tool description
- Input schema
→ 이게 7,000-8,000 tokens일 수 있음!

### **즉시 할 일:**
1. `llm.py`의 `_get_tools()` 확인
2. Tool 스키마 크기 측정
3. Tool 정의 최적화
   - Description 압축
   - Schema 단순화

### **예상 최적화:**
- Tool 스키마: 7,000 → 500 tokens (93% 절감!)
- 총 입력: 9,340 → 2,000 tokens (79% 절감!)
- Turn 비용: $0.035 → $0.008 (77% 절감!)
"Day 6 UsageTracker 실제 플레이 완료!

충격적 발견:
- 입력 토큰: 8,000개 (예상 1,500개)
- Turn당 비용: $0.031 (예상 $0.025보다 24% 비쌈)

문제:
어디선가 6,500 tokens가 추가로 들어감.
시스템 프롬프트 디버깅 필요.

즉시 할 일:
1. 프롬프트 각 부분 토큰 수 측정
2. 병목 지점 파악
3. 긴급 최적화

프로젝트 경로: /Users/leejy/Desktop/engine/
위 전체 컨텍스트 참고해서 디버깅 시작하자!"
```
        """
        logger.debug(f"Total prompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)")
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
