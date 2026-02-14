# Living World Engine - 개발 일지

> 4주 개발 과정을 기록하는 문서
> 시작일: 2025-02-15 (토) / 마감일: 2025-03-15 (토)

---

## 진행 현황

| 주차 | 목표 | 상태 | 테스트 |
|------|------|------|--------|
| **Week 1** (2/15~2/21) | 핵심 엔진 + LLM 통합 | 🔴 진행중 | 85/85 pass |
| **Week 2** (2/22~2/28) | 이벤트 + 루프 방지 | ⬜ 예정 | - |
| **Week 3** (3/1~3/7) | 세계관 + API | ⬜ 예정 | - |
| **Week 4** (3/8~3/14) | UI + 문서 + 데모 | ⬜ 예정 | - |

---

## Week 1: 핵심 엔진 구축

### Day 1 (2/15 토) ✅

**작업 내용:**
- Poetry 프로젝트 초기화 (Python 3.11 + 의존성 설치)
- MASTER_PLAN 기반 프로젝트 구조 생성
- 핵심 엔진 모듈 6개 구현
  - `state.py` — WorldState 상태 관리 (관계 수치 0-100 클램핑, NPC 조회, 스냅샷)
  - `memory.py` — KeywordMemorySearch (키워드 50% + 중요도 30% + 최신도 20% 가중치)
  - `llm.py` — ClaudeClient (Tool Use 2단계 호출 구현)
  - `validator.py` — StateChangeValidator (변화량 -10~+10 제한, 캐릭터 존재 검증)
  - `loop_detector.py` — LoopDetector (상태 정체 + 대사 반복 감지)
  - `events.py` — EventManager (스텁, Week 2에서 완성)
- 메인 게임 루프 `game_loop.py` 작성 (전체 턴 플로우 연결)
- ai_s에서 세계관 데이터 추출 및 재구성
  - NPC 6명: 엘레나, 벨라, 루아, 세인, 록산느, 레오 (스킬 포함)
  - 이벤트 10개: 중간고사, 결투, 축제, 각성 등
- 유닛 테스트 53개 작성 및 전부 통과
  - test_state.py (14개) — 상태 관리 전반
  - test_memory.py (9개) — 메모리 검색 + 키워드 매칭
  - test_validator.py (9개) — 검증 로직 + 클램핑
  - test_loop_detector.py (6개) — 루프 감지
  - test_llm.py (15개) — Mock 기반 Tool Use 검증
- Claude API 테스트 3/3 통과 (기본 호출, Tool Use, 대화 컨텍스트)
- Git 초기화 + 첫 커밋

**기술적 결정:**
- LangChain 사용 안 함 → Anthropic API 직접 사용 (완전한 제어)
- GPT-4o-mini → Claude Sonnet 4.5 전환 (Tool Use 품질 + 포트폴리오 차별화)
- PostgreSQL/Redis → JSON 파일 (Week 1-2는 가볍게, 필요시 마이그레이션)
- ai_s의 3-Layer + FSM 구조 → 단일 GameEngine 루프 (단순화)
- ai_s의 태그 파싱 방식 → Tool Use 구조화 JSON (파싱 에러 원천 차단)

**ai_s 대비 개선점:**
- NPC intent "challenge" 고착 → FSM 제거, LLM이 맥락 보고 직접 반응
- StoryLLM 반복 루프 → LoopDetector가 정체 감지
- Reducer 우선순위 충돌 → 단일 파이프라인 (LLM → Validator → State)
- 이벤트 중복 → 쿨다운 시스템
- 테스트 부족 → 53개 유닛 테스트 (Mock LLM 포함)

**커밋:**
```
65563e7 feat: Day 1 complete - Core engine & Claude API integration
35 files, 2,703 insertions
```

---

### Day 2 (2/16 일) ✅

**목표:** 세계관 로딩 + 통합 테스트 + 프롬프트 튜닝

**완료:**
- [x] WorldState.load_from_file() 클래스 메서드 구현
  - world.json, characters.json 두 파일 분리 로딩
  - 3단계 에러 처리: FileNotFoundError, JSONDecodeError, ValueError(필수 필드 누락)
  - GameEngine.initialize() 연동 수정
  - 유닛 테스트 5개 추가 (정상 로딩, 파일 없음, 잘못된 JSON, 필수 필드 누락, 다수 NPC)

- [x] GameEngine 통합 테스트 (실제 Claude API 호출)
  - `backend/tests/integration/test_game_engine.py` 생성
  - pytest.mark.integration 마커 분리
  - 단일 턴 테스트 4개: 응답 존재, Tool Use 발생, 상태 업데이트, 한국어 응답
  - 멀티 턴 테스트 1개: 2턴 대화에서 이름 기억 확인
  - 5/5 전부 통과

- [x] 빈 응답 버그 수정 (llm.py)
  - 문제: Claude 2차 호출에서 빈 텍스트 반환되는 케이스
  - 원인: tool_result 메시지에 대사 생성 유도 힌트 없음
  - 해결: tool_result에 "이제 NPC의 대사로 응답하세요" 추가 + 1차 텍스트 fallback

- [x] 시스템 프롬프트 1차 튜닝 (game_loop.py)
  - `_build_system_prompt()` 전면 개선
  - `_format_npc_profiles()` 신규 — 전체 NPC 데이터(persona, speech_style, skills) 반영
  - `_format_memories()` 신규 — 감정 + 중요도 표시

**프롬프트 튜닝 Before → After:**

| 항목 | Before | After |
|------|--------|-------|
| 응답 형식 | RPG 소설체, 3인칭 서술 | 대화 중심, 괄호 행동, 2~4문장 |
| 캐릭터성 | NPC 이름+역할만 전달 | persona + speech_style + skills + 관계 수치 전부 전달 |
| 장면 설정 | `**[장소명]**` 헤더 + 풍경 묘사 | 장면 헤더 금지, 바로 대사로 시작 |
| Tool Use | "관계 변화 -10~+10" | 세분화: 인사 ±1~2, 호의 +3~5, 중요도 기준 명시 |
| 기억 | "새 기억 최소 1개" | 중요도 가이드: 인사=2~3, 대화=4~6, 감정 사건=7~9 |

**실제 응답 비교:**

Before:
```
**[아케인 아카데미 결투장]**
따뜻한 봄 햇살이 결투장을 비추고 있었다. 엘레나는 우아하게 앉아
노트를 보고 있었는데, 은발이 바람에 흔들리며...
```

After:
```
(결투장 벤치에서 책을 덮으며 고개를 든다) "어머, 신입생이군요.
준영이라... 기억해 두죠." (차가운 눈빛으로 훑어본다)
```

**테스트:**
- 유닛: 53 → 58개 (+5 load_from_file)
- 통합: 0 → 5개 (+5 GameEngine 실제 API)
- 총: **63개** (100% 통과)

**커밋:**
```
f4b7b16 feat: Add WorldState.load_from_file() with comprehensive validation
+ feat: Add GameEngine integration tests with real Claude API
+ feat: System prompt tuning for natural dialogue + empty response fix
```

**API 비용:** ~$0.50 (통합 테스트 약 10회 실행)

**다음 (Day 3):**
- [ ] EventManager 기본 구현 (조건 평가 로직)
- [ ] 조건 기반 이벤트 트리거
- [ ] 이벤트-상태 연동 테스트

---

### Day 3 (2/17 월) ✅

**목표:** EventManager 완성 + GameEngine 연동

**완료:**
- [x] EventManager 전체 구현 (events.py)
  - `load_events_from_file()` — JSON 로딩 + 에러 처리
  - `check_events()` — 3가지 조건 평가 (turn_range, variable_threshold, relationship_threshold)
  - `trigger_event()` — 쿨다운 설정 + 히스토리 기록
  - 연산자 6종 지원: >=, >, <=, <, ==, !=
  - 유닛 테스트 15개
- [x] GameEngine ↔ EventManager 연동 (game_loop.py)
  - `initialize()` — events.json 자동 로딩
  - `process_turn()` — 이벤트 체크 → 발동 → 쿨다운 → `events_triggered` 반환
  - Mock LLM 기반 연동 테스트 7개

**테스트:** 63 → **85개** (+15 EventManager, +7 연동)

**다음 (Day 4):**
- [ ] LoopDetector → EventManager 강제 이벤트 주입
- [ ] 이벤트 effects 적용 (world_variable, player_stat 변경)
- [ ] 10턴 E2E 테스트

---

### Day 4-5 ⬜

**예정:**
- [ ] 이벤트 effects 적용 로직
- [ ] LoopDetector 고도화 (루프 감지 시 이벤트 주입)
- [ ] ClaudeClient 에러 재시도

### Day 6-7 ⬜

**예정:**
- [ ] 10턴 E2E 테스트
- [ ] Week 1 마무리 + 버그 수정

---

## Week 2: 고도화 & API

### Day 8-10 ⬜
- [ ] FastAPI 엔드포인트 구현
- [ ] API 테스트

### Day 11-12 ⬜
- [ ] CLI 또는 간단한 웹 클라이언트
- [ ] 수동 플레이 테스트

### Day 13-14 ⬜
- [ ] 버그 수정 + 성능 최적화
- [ ] Week 2 마무리

---

## Week 3: 세계관 & API

### Day 15-17 ⬜
- [ ] 세계관 로더 구현
- [ ] NPC 3명 추가 정의
- [ ] 이벤트 확장

### Day 18-19 ⬜
- [ ] FastAPI 엔드포인트 구현
- [ ] API 테스트

### Day 20-21 ⬜
- [ ] CLI 테스트 클라이언트
- [ ] 수동 테스트 + 버그 수정

---

## Week 4: UI & 마무리

### Day 22-24 ⬜
- [ ] React UI (또는 CLI 폴리싱)

### Day 25-26 ⬜
- [ ] 버그 수정 + 성능 최적화

### Day 27-28 ⬜
- [ ] 문서 작성
- [ ] 데모 비디오 촬영
- [ ] GitHub 정리 + 제출

---

## 기존 버전(ai_s) vs 새 엔진 — 차이점 & 발전점

### 배경

이 프로젝트는 처음부터 만든 것이 아닙니다.
기존에 `ai_s` → `ai_s_v1` → `ai_s_v2`까지 3번의 시도가 있었고,
각 버전에서 발견한 문제점과 교훈을 바탕으로 **새로 설계**한 것이 이 Living World Engine입니다.

> "복잡한 시스템을 분석하고, 핵심만 남겨서 더 나은 버전을 만들었다."

---

### 아키텍처 변화

| 영역 | ai_s (기존) | 새 engine | 왜 바꿨나 |
|------|-------------|-----------|-----------|
| **전체 구조** | 3-Layer (Narrative / Interpretation / World) + Orchestrator, ~75파일 | 단일 GameEngine 루프, ~35파일 | 레이어 간 충돌이 디버깅 불가능 수준이었음 |
| **NPC 행동** | FSM 상태머신 (npc_behavior.py + behavior_arbitrator.py) | LLM에게 위임 (Tool Use) | FSM이 플레이어 행동을 반영 못해 항상 "challenge"로 고착 |
| **상태 변경** | LLM 텍스트 → 태그 파싱 (`<NPC_EMOTION>`, `<RELATION>`) | LLM이 Tool Use로 구조화된 JSON 직접 반환 | 태그 파싱 실패율이 높았고 디버깅 어려움 |
| **상태 적용** | StateReducer (다중 소스 diff 병합, 우선순위 충돌) | 단일 파이프라인: LLM → Validator → State | Reducer에서 LLM 결과가 NPC behavior에 덮어씌워지는 버그 |
| **프롬프트** | prompt_npc_compiler.py, prompt_world_compiler.py 별도 파일 | GameEngine._build_system_prompt() 통합 | 분산된 프롬프트가 일관성 문제 유발 |

---

### LLM 전환

| | ai_s | 새 engine |
|---|---|---|
| **모델** | OpenAI GPT-4o-mini | Anthropic Claude Sonnet 4.5 |
| **라이브러리** | openai + httpx (프록시) | anthropic (공식 SDK 직접) |
| **호출 방식** | 1회 호출 → 텍스트에서 태그 수동 추출 | 2단계 호출 (tool_use → tool_result → 최종 텍스트) |
| **응답 구조** | 비구조적 텍스트 (파싱 필요) | 구조화된 JSON (파싱 불필요) |

**전환 이유:**
1. Claude의 Tool Use가 GPT보다 안정적이고 스키마 준수율이 높음
2. 포트폴리오에서 "GPT 말고 다른 LLM도 써봤다"는 차별화
3. LangChain 없이 직접 구현 → 면접에서 동작 원리 설명 가능

---

### 기존 5대 버그 → 해결 방법

#### 1. NPC intent "challenge" 고착
```
[기존] NPCBehaviorEngine의 FSM이 intent를 계산하지만,
       플레이어 행동(선물, 대화 등)이 반영되지 않아 항상 "challenge"로 리셋
[해결] FSM 자체를 제거. LLM이 대화 맥락과 관계 수치를 보고 직접 반응.
       Validator가 변화량만 제한하므로 LLM의 자유도와 게임 밸런스를 동시에 확보.
```

#### 2. StoryLLM "증거 불충분" 반복
```
[기존] world_diff에 변화가 적으면 StoryLLM이 "증거가 부족합니다"를 반복
       프롬프트에 변화 강제 지시가 없었음
[해결] LoopDetector가 상태 정체(5턴간 변화량 < 임계값)를 감지하면
       EventManager가 강제 이벤트를 주입하여 서사를 전환.
       시스템 프롬프트에 "매 턴 반드시 상태 변경을 제안하라" 명시.
```

#### 3. 한국어 액션 파서 키워드 부족
```
[기존] action_parser.py에서 한국어 키워드를 하드코딩
       ("싸우다", "때리다" 등 제한된 단어만 인식)
       "도전장을 내밀다", "결투를 신청하다" 같은 표현 미인식
[해결] 액션 파서 자체를 제거. 플레이어 입력을 그대로 LLM에 전달.
       LLM이 자연어를 직접 이해하고 적절한 상태 변경을 Tool Use로 제안.
```

#### 4. Reducer 우선순위 충돌
```
[기존] StateReducer가 여러 소스(LLM, NPC behavior, Rule engine)의 diff를 병합
       우선순위: npc_behavior > story_llm → LLM의 관계 변화가 무시됨
[해결] 상태 변경 소스를 LLM 하나로 통일.
       LLM → Validator(검증) → WorldState.apply_changes(적용)
       단일 파이프라인이므로 충돌 자체가 불가능.
```

#### 5. 이벤트 중복 누적
```
[기존] confession_event가 조건 충족 시 매 턴 트리거되어 10개 이상 쌓임
       중복 체크 로직 없었음
[해결] EventManager에 cooldown 딕셔너리 도입.
       이벤트 트리거 시 해당 이벤트의 쿨다운 설정 (예: 15턴).
       tick_cooldowns()로 매 턴 감소, 0이 될 때까지 재트리거 차단.
```

---

### 데이터 저장 전략 변화

| | ai_s | 새 engine (현재) | 새 engine (예정) |
|---|---|---|---|
| **상태** | PostgreSQL `world_state` 테이블 | JSON 파일 (`saves/`) | SQLite (필요시) |
| **메모리** | PostgreSQL `npc_memory` 테이블 | Python dict (인메모리) | JSON 파일 저장 |
| **세션** | PostgreSQL `player_sessions` 테이블 | 파일 기반 | SQLite (필요시) |
| **캐시** | Redis (최근 서사 요약) | 없음 (불필요) | 없음 |
| **실행 준비** | Docker Compose (PostgreSQL + Redis + App) | `poetry install`만 하면 끝 | 동일 |

**변경 이유:**
- Week 1-2는 빠른 프로토타입이 중요 → 외부 의존성 최소화
- "처음엔 JSON으로 MVP, 나중에 DB 마이그레이션" = 설계 진화 과정을 보여줌
- PostgreSQL/Redis는 이 규모에서 과도한 설계 (over-engineering)

---

### 테스트 전략 변화

| | ai_s | 새 engine |
|---|---|---|
| **테스트 수** | 6개 파일 (유틸 위주) | **53개** (핵심 로직 전부) |
| **LLM 테스트** | 없음 (실제 API 의존) | **Mock 기반 15개** (API 없이 검증) |
| **커버리지** | 측정 안 함 | **pytest-cov 설정 완료** |
| **방식** | 코드 먼저 → 테스트 나중 | **테스트와 코드 동시 작성 (TDD)** |

---

### 세계관 데이터 활용

기존 ai_s에서 **검증된 세계관 데이터**를 가져와 새 구조에 맞게 재편성:

| 가져온 것 | 원본 | 변환 |
|-----------|------|------|
| NPC 6명 | `configs/worlds/academy.json`의 npc_templates | `characters.json` (skills, speech_style 추가) |
| 세계관 설정 | `configs/worlds/academy.json`의 world_variables | `world.json` (구조 정리) |
| 이벤트 | `configs/world_events.json`의 lambda 조건식 | `events.json` (선언적 JSON 조건으로 변환) |
| 말투 프로필 | `configs/npc_tone_profiles.json` | `characters.json`의 speech_style에 통합 |

**핵심 변화:** 기존의 lambda 문자열 조건 → 선언적 JSON 조건으로 변환
```
기존: "condition": "lambda w: w.get('world', {}).get('variables', {}).get('chaos_level', 0) > 0.7"
새것: "condition": {"type": "variable_threshold", "variable": "chaos_level", "op": ">=", "value": 0.7}
```
→ eval() 보안 위험 제거, JSON Schema로 검증 가능

---

### 한 줄 요약

> ai_s는 "모든 것을 시스템으로 만들자"는 접근 → 복잡성 폭발, 디버깅 불가
> 새 engine은 "LLM에게 맡길 건 맡기고, 검증만 확실히"는 접근 → 단순하지만 안정적

---

## 누적 통계

| 지표 | 값 |
|------|-----|
| 총 커밋 | 9 |
| 총 테스트 | 85 (유닛 80 + 통합 5) |
| 테스트 통과율 | 100% |
| Python 파일 | ~24개 |
| JSON 데이터 | 3개 (world, characters, events) |
| NPC 수 | 6명 |
| 이벤트 수 | 10개 |
| API 비용 (누적) | ~$0.52 |

---

## 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| LLM | Claude Sonnet 4.5 | Tool Use 품질, 포트폴리오 차별화 |
| Backend | FastAPI | 비동기 + 자동 문서화 |
| 의존성 | Poetry | 모던 Python 패키지 관리 |
| 테스트 | pytest + pytest-mock | Mock 기반 LLM 테스트 |
| 저장소 | JSON (→ SQLite 예정) | 빠른 프로토타입 |
| Frontend | React (예정) | 시간 부족 시 CLI 대체 |
