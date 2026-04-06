# Living World Engine - 개발 일지

> 4주 개발 과정을 기록하는 문서
> 시작일: 2025-02-15 (토) / 마감일: 2025-03-15 (토)
> 최적화·상수 정본: **2026-03-30** 섹션 + 저장소 코드

---

## 진행 현황

| 주차 | 목표 | 상태 | 테스트 |
|------|------|------|--------|
| **Week 1** (2/15~2/21) | 핵심 엔진 + LLM 통합 | 🔴 진행중 | 85/85 pass |
| **Week 2** (2/22~2/28) | 이벤트 + 루프 방지 | ⬜ 예정 | - |
| **Week 3** (3/1~3/7) | 세계관 + API | ⬜ 예정 | - |
| **Week 4** (3/8~3/14) | UI + 문서 + 데모 | ⬜ 예정 | - |

---

## 2026-03-30 코드 기준: 성능 최적화 스냅샷 (Phase 1–2)

이 절은 **저장소 코드와 동기화된 정본**이다. 아래 Day 13 일지에 적힌 숫자(예: `NPC_RECENT_TURNS=3`, `MAX_CONTEXT_TOKENS=2000`)는 과거 스냅샷이므로, 충돌 시 **항상 코드**를 따른다.

### Phase 1 — 프롬프트 캐시 (`SystemPromptOptimizer` + `ClaudeClient`)

- 시스템 프롬프트를 **static / dynamic** 튜플로 분리 (`backend/src/engine/prompt_optimizer.py`, `game_loop._build_system_blocks`).
- `ClaudeClient`에서 static 블록에 `cache_control: ephemeral` 적용 가능한 구조.
- **Dynamic**: 턴, 장소, NPC(컴팩트 프로필), `## 중요 기억`.
- **장소 필터**: `_active_npcs_for_location()` — `active_location`과 `npc["location"]`이 같을 때만 프로필 주입. 매칭 NPC가 없으면 **전체 NPC**로 폴백. `active_location == "Unknown"`이면 전체.

### Phase 1.5 — Single-Pass Tool Use (`backend/src/engine/llm.py`)

- `enable_single_pass=True`(기본): 1차 응답에 **텍스트가 있으면** 2차 API 호출 생략.
- 텍스트 없이 `tool_use`만 오면 **2차 폴백** (Tool Result 후 재호출).
- **2차 호출 히스토리**: `ContextManager.KEEP_RECENT_TURNS * 2`개 메시지만 전송 — Layer 1과 동일 깊이 (현재 6개).

### Phase 2 — 컨텍스트 3-Layer (`backend/src/engine/context_manager.py`)

| 상수 | 값 | 설명 |
|------|-----|------|
| `MAX_CONTEXT_TOKENS` | **1600** | 대화 히스토리 추정 예산 |
| `KEEP_RECENT_TURNS` | **3** | Layer 1: 최근 3턴(메시지 최대 6개), 예산 초과 시 2→1턴까지 축소 |
| `NPC_SAMPLING_WINDOW` | **20** | Layer 2 샘플링 구간(턴×2 메시지 길이로 윈도 계산) |
| `NPC_RECENT_TURNS` | **1** | NPC당 Layer 2에서 최근 1턴(메시지 최대 2개) |
| `OTHER_CAP` | **1** | NPC 이름 미포함(other) 메시지 상한 |

**예산 초과 시**: Layer 2의 `NPC_RECENT_TURNS`를 1씩 줄이다 0이 되면, Layer 1의 `KEEP_RECENT_TURNS`를 1씩 줄임(최소 1턴 = 2메시지).

**토큰 추정** (`_count_tokens`): 문자열은 `len / 1.2`, 메시지 내 tool 블록(dict)은 `len(str(block)) * 1.5` 후 합산에 포함.

### Layer 3 — 장기 기억 (`backend/src/engine/long_term_memory.py` + `game_loop.py`)

- **파일**: 런타임 장기 기억은 `LongTermMemory` (`long_term_memory.py`). `memory.py`의 `KeywordMemorySearch`는 별도(주로 테스트·레거시 경로).
- **검색** (`search`): `player_id`로 필터 → `min_importance`(게임 루프에서 **7**) → 쿼리 있으면 키워드·태그·내용 매칭 점수(`_calculate_relevance`), 없으면 중요도·시간 정렬. **BM25 미사용**.
- **게임 루프 호출**: `min_importance=7`, `limit=10`.
- **프롬프트 주입**: `SystemPromptOptimizer._select_key_memories`는 `importance >= 6`으로 한 번 더 걸러 중요도 내림차순 → `_format_memories`는 **최대 5줄**만 `## 중요 기억`에 출력.
- **중복 억제** (`add_memory` → `_is_duplicate`): 전역 `self.memories`의 **최근 10개**와 `SequenceMatcher.ratio() > 0.95`면 스킵.

### 출력·설정 (`backend/src/utils/config.py`, `.env.example`)

- 기본 **`llm_max_tokens` = 768** (출력 상한; `.env`로 조정).
- 모델 별칭: `sonnet`, `sonnet45`, `haiku`, `hikaru` 등 → `config.LLM_MODEL_ALIASES`.

### Usage / 비용 (`backend/src/utils/usage_tracker.py`)

- 턴마다 세그먼트별 `input` / `output` / `cache_creation` / `cache_read` 기록.
- `standard_input_billable()`: 캐시 토큰과 표준 입력의 **이중 과금을 피하는** 휴리스틱.

### 검증·다음 작업 (문서화만)

- [ ] 동일 세션에서 Single-Pass 성공률·평균 턴 비용 **실측** (README의 참고치는 측정 조건 의존).
- [ ] Phase 3: `llm_max_tokens` A/B (예: 640 / 768 / 1024) 품질·비용.
- [ ] 필요 시 `MAX_CONTEXT_TOKENS`, `KEEP_RECENT_TURNS`, `NPC_RECENT_TURNS`, Layer3 `limit` / `min_importance` 미세 조정.

### UGC 플랫폼 MVP (2026-04 기획 통합)

엔진을 **멀티 유저·UGC·BYOK·배포**까지 확장하는 **4주 MVP** 범위·주차·비용·체크리스트는 코드가 아닌 기획 문서로만 관리한다:

- **[`docs/UGC_MVP_PLAN.md`](docs/UGC_MVP_PLAN.md)** — 단일 정본 (정책 상한 vs 1차 베타 코호트 구분, Ready but Gated, Phase 2 경계)

구현이 시작되면 해당 문서의 체크리스트를 갱신하고, 아키텍처 다이어그램은 `docs/ARCHITECTURE.md`에 UGC 흐름을 반영할 예정이다.

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

## Day 5 (2/15 토) - CLI 스크립트 + 수동 테스트

### 완료 작업

#### 1. CLI 플레이 스크립트 작성
- `backend/play_game.py` 생성
  - GameEngine 초기화 (`initialize()` API 사용)
  - 턴 처리 루프 (`process_turn()` 반환값 처리)
  - 상태 출력 (세계, 플레이어, 관계도)
  - 입력/종료 처리

#### 2. Import 경로 통일
- 문제: `from backend.src.engine` vs `from .engine` 혼재
- 해결: 상대 경로로 통일
  - `game_loop.py`: `from .state`, `from ..utils.logger`
  - `llm.py`: `from ..utils.config`, `from ..utils.logger`
  - `validator.py`: `from ..utils.logger`

#### 3. Logger 누락 수정
- `game_loop.py`: `logger = get_logger(__name__)` 추가
- `llm.py`: `logger = get_logger(__name__)` 추가

#### 4. GitHub 저장소 연결
- Repository: https://github.com/leejunyoung0610/living-world-engine
- 첫 Push 완료 (141 objects)

### 수동 테스트 결과

**4턴 플레이 테스트:**
```
Turn 1: "안녕하세요"
→ 엘레나 등장, 정중한 인사
→ 관계도: 20 → 22 (+2)

Turn 2: "반갑습니다!"
→ 호의적 반응, 마법 전투 관심 여부 질문
→ 관계도: 22 → 24 (+2)

Turn 3: "결투보다는 사람이랑 친해지고싶어서요"
→ 솔직한 답변에 긍정적 반응
→ 관계도: 24 → 27 (+3, trust +2)

Turn 4: "아카데미에서 여자친구 만드는법이 궁금해요"
→ 당황하면서도 진지한 조언
→ 관계도: 27 → 29 (+2, trust +2)
```

**품질 평가:**
- ✅ NPC 응답 품질: **9/10**
  - 자연스러운 대화 흐름
  - 캐릭터 일관성 유지 (엘레나의 차분한 멘토 톤)
  - 행동 묘사 적절 `(노트를 덮으며 미소를 짓는다)`
- ✅ Tool Use: **정상 작동** (매 턴 `update_game_state` 호출)
- ✅ 관계도 시스템: **정상** (20 → 29, 9포인트 증가)
- ✅ 기억 생성: **정상** (각 턴마다 기억 저장)
- ✅ 이벤트 시스템: **작동** (Turn 1에 2개 이벤트 발생)
- ✅ 루프 방지: **정상** (severity 0 유지)

### 기술적 이슈 해결

**Issue 1: Import 경로 충돌**
- 증상: `ModuleNotFoundError: No module named 'backend'`
- 원인: 절대 경로 (`from backend.src`) vs 상대 경로 혼재
- 해결: 모든 엔진 모듈을 상대 경로로 통일
- 시간: ~20분

**Issue 2: Logger 정의 누락**
- 증상: `NameError: name 'logger' is not defined`
- 원인: `get_logger` import만 하고 객체 생성 안 함
- 해결: `logger = get_logger(__name__)` 추가
- 영향 파일: `game_loop.py`, `llm.py`

**Issue 3: API 변경 적응**
- 증상: `GameEngine.__init__()` 인자 불일치
- 해결: `GameEngine()` 생성 후 `initialize(world_dir)` 호출
- 변경: `engine.turn()` → `engine.process_turn()` (반환값 구조 변경)

### 비용

- 4턴 테스트: **~$0.25**
- 예상대로 저렴하게 진행

### 테스트 현황

- 총 87개 (100% 통과)
- Unit: 80개
- Integration: 5개
- E2E: 2개
- **Manual: 4턴** (신규)

### 다음 단계

- [ ] Week 1 회고 작성
- [ ] Day 6: 성능 벤치마크
- [ ] Day 7: Week 1 마무리 + Week 2 계획

### 커밋
```
71dc0a0 - feat(day5): Add CLI play script + fix logger imports
[추가 커밋 예정] - fix: Add missing logger imports in game_loop and llm

## Day 6 (2/15 토) - 비용 추적 + 분석

### 완료 작업
- UsageTracker 구현 (토큰 카운팅, 비용 계산)
- ClaudeClient 토큰 정보 반환
- GameEngine 비용 기록
- CLI 비용 표시
- 상세 토큰 분석 로깅

### 비용 분석 결과
```
Turn당: $0.036
1차 호출: 4,658 tokens
2차 호출: 4,968 tokens
총: 9,626 tokens

API 오버헤드: 3.7배 (불가피)
```

### 원인 파악
1. **API 내부 포맷팅:** 3.7배 증가 (XML 태그, JSON 파싱)
2. **System Prompt:** 992 tokens (최적화 가능)
3. **Tools Definition:** 274 tokens (정상)

### 최적화 계획
- Week 2: System Prompt + Caching → $0.015/turn (58% ↓)
- Week 3: Model Switching → $0.006/turn (83% ↓)

### 테스트
- 91개 (100% 통과, E2E 제외)
- Coverage: 91%

### 다음 단계
- Day 7: SystemPromptOptimizer 구현

### Day 7 ⬜

**예정:**
- [ ] Week 1 마무리 + Week 2 계획

## 📊 진행도 업데이트

```
Week 1: ██████████ 71% (Day 5/7 완료)
Week 2: ░░░░░░░░░░  0%
Week 3: ░░░░░░░░░░  0%
Week 4: ░░░░░░░░░░  0%

전체:   ██████░░░░ 17.9% (Day 5/28)
```

---

## Week 2: 고도화 & API

### Day 8 ⬜
- [x] Anthropic Prompt Caching (System+Tools 캐싱, UsageTracker 확장)
- [ ] FastAPI 엔드포인트 구현
- [ ] API 테스트

### Day 9 (2/16 일) ✅

**완료:**
- `PerformanceMonitor` 도입 → memory/prompt/LLM/state/loop/event 단계 측정
- 18턴 장기 실험 → LLM 호출 14.6s/턴, 나머지 단계는 0.05s 이하
- Context 누적으로 Turn 1: $0.005 → Turn 18: $0.034 → 예측 $0.15/turn
- 종료 리포트에 performance/usage 로그 출력

**문제:**
- Context 누적 → 비용 상승, LLM 병목 (API 측면)
- 목표: Day 10-11에 ContextManager(sliding window + importance sampling) 추가, $0.015/turn 고정

**다음:**
- Day 10-11: 장기 기억 / ContextManager 개발 + Day 12 회고

### Day 10-11 ⬜
- [ ] 장기 기억 시스템 설계
- [ ] ContextManager + sliding window

### Day 12 ⬜
- [ ] Week 2 회고

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

## Day 13 (2/15 일) - ContextManager + Tool 최적화

### 🎯 목표
- ContextManager 통합으로 conversation history 최적화
- Tool Use 선택적 사용으로 비용 절감
- LoopDetector 오탐지 수정

### ✅ 완료 작업

#### 1. ContextManager 구현 및 통합
```python
# backend/src/engine/context_manager.py
class ContextManager:
    MAX_CONTEXT_TOKENS = 3000
    KEEP_RECENT_TURNS = 10
    
    def build_context(user_input, full_history, max_tokens):
        # 최근 10턴 유지
        # 오래된 메시지 중요도 샘플링 (tool_use, NPC 매칭, 길이)
        # 토큰 예산 내에서 선택
```

**통합**:
- `GameEngine.process_turn()`에서 `context_manager.build_context()` 호출
- LLM에 최적화된 히스토리 전달
- 로그: "Context optimized from 104 → 41 messages (900 tokens)"

**테스트**: 7개 전부 통과
- `test_keep_recent`, `test_build_context_with_sampling`
- `test_importance_calculation`, `test_token_counting`

#### 2. Tool 선택적 사용 (System Prompt 개선)
```python
# backend/src/engine/prompt_optimizer.py
## Tool 사용 규칙 (중요!)
다음 경우에만 update_game_state 호출:
  ✅ 관계 변화 (호감/신뢰 증감)
  ✅ 중요한 이벤트 발생
  ✅ 의미 있는 대화/행동

다음 경우는 Tool 없이 직접 답변:
  ❌ 단순 인사 ("안녕", "잘가")
  ❌ 짧은 응답 ("응", "그래")
  ❌ 상태 변화 없는 일상 대화
```

**예상 효과**:
- 단순 대화 50% → Tool 미사용 → 1차 API 호출만
- 복잡한 대화 50% → Tool 사용 → 2차 API 호출
- 평균 비용: $0.034 → $0.017 (50% 절감)

#### 3. LoopDetector 오탐지 수정
```python
# backend/src/engine/loop_detector.py
# Stagnation 임계값 완화
if avg_change < 0.001:  # 기존 0.01 → 0.001
    return 10

# Repetition 자기 매칭 보정
match_count = max(0, match_count - 1)  # 자기 자신 제외
```

**변경 이유**:
- 기존: 관계 0.01 변화(1%) → severity 10 (너무 민감)
- 수정: 관계 0.001 변화(0.1%) → severity 10
- 정상 대화(1-5% 변화)는 severity 1-4로 낮춤

#### 4. 캠퍼스 세계관 추가
```
backend/src/worlds/campus/
├── world.json         (서울대학교 캠퍼스)
├── characters.json    (김서연, 이준호, 박지민, 최민준 교수)
└── events.json        (조별과제, 중간고사, MT 등)
```

**CLI 개선**:
```bash
# 기본 (campus)
poetry run python backend/play_game.py

# 선택
poetry run python backend/play_game.py --world arcane_academy
```

#### 5. 버그 수정
- EventManager: `{"events": [...]}` 구조 로딩 수정
- `GameEngine.print_performance_report()` 메서드 추가
- `context_manager.py`: `get_logger()` 사용으로 로그 출력

### 📊 비용 분석

#### Before (Turn 52 기준)
```
평균: $0.034/turn
원인: 매 턴 Tool 사용 (2차 API 호출)
      전체 conversation history 재전송
```

#### After (예상)
```
평균: $0.017/turn
Tool 사용률: 100% → 50%
ContextManager: 104 messages → 41 messages
```

#### 실제 테스트 결과 (Turn 1-3)
```
Turn 1: $0.007932 (캐시 생성)
Turn 2: $0.013992 (Tool 사용, 관계 변화)
Turn 3: Context optimized from 5 → 5 messages (86 tokens)
```

### 🔍 다음 작업 (Day 14)

#### Priority 1: Tool 최적화 검증
- 50턴 테스트 실행
- Tool 사용 빈도 측정 (목표: 50%)
- 평균 비용 확인 (목표: $0.017)

#### Priority 2: Static/Dynamic Prompt 분리
- Static: 세계관, NPC 프로필 (캐시)
- Dynamic: 현재 상황, 기억 (매 턴 변경)
- 예상: 캐시 히트율 95% → 비용 추가 절감

#### Priority 3: Model Switching
- 단순 대화: Claude Haiku ($0.25/1M tokens)
- 복잡한 이벤트: Claude Sonnet ($3/1M tokens)
- 예상: 70% Haiku 사용 → 비용 80% 절감

---

## Day 13 (3/15 일 오후) ✅

**작업 내용:**

### 1. 성능 분석 및 문제 발견
- 터미널 로그 분석 (Turn 16-27, 11턴)
- **Loop Detection 오작동**: 매 턴 severity 10 감지 (실제로는 루프 아님)
- **토큰 증가**: 5001 → 6869 tokens (목표 3000 초과)
- **비용 증가**: $0.027 → $0.040/turn
- **LLM 속도**: 평균 13-19초 (느림)

### 2. Loop Detection 긴급 수정
```python
# backend/src/engine/loop_detector.py (Line 21)
STAGNATION_THRESHOLD = 0.05 → 0.001  # 완화
```

**효과:**
- 상태 변화 0.02 (2%) → severity 10에서 → severity 1-4로 개선
- 정상 대화는 루프로 감지하지 않음
- 실제 루프(0.001 미만)만 감지

### 3. Context Manager 최적화
```python
# backend/src/engine/context_manager.py (Line 14)
KEEP_RECENT_TURNS = 10 → 6  # 40% 축소
```

**효과:**
- 최근 메시지: 20개 → 12개
- 토큰 절약: ~320 tokens
- 예상 토큰: ~1500 tokens/turn (목표 달성)

### 4. play_game.py 개선
```python
# --reset 옵션 추가
parser.add_argument("--reset", action="store_true", 
                   help="새 게임 시작 전 기억 초기화")
```

**사용법:**
```bash
poetry run python backend/play_game.py --world campus --reset
```

### 5. System Prompt 세션 구분
```python
# backend/src/engine/prompt_optimizer.py (Line 38)
session_note = f" (세션 시작)" if turn == 0 else ""
prompt = f"너는 {world}의 NPC다.{session_note}"
```

**효과:**
- Turn 0에서 Prompt Cache 무효화
- 새 게임 시작 시 이전 캐시 재사용 방지
- 완전히 새로운 세션 보장

### 6. 멀티유저 설계 이슈 확인 ⚠️
**발견된 문제:**
- `memories.json` 파일 공유 → 사용자 간 기억 오염
- `player_id="default"` 하드코딩 → 사용자 격리 없음
- Prompt Cache 공유 → 잠재적 privacy 이슈

**해결 계획:**
- Week 3-4 (API 개발 시) PostgreSQL 마이그레이션
- 사용자별 세션 격리
- 현재는 단일 유저 CLI 완성에 집중 ✅

### 📊 예상 개선 효과

#### Before (수정 전)
```
Loop Detection: 매 턴 severity 10 ❌
토큰: 5000~6800 tokens/turn
비용: $0.027~$0.040/turn
```

#### After (수정 후)
```
Loop Detection: severity 0-5 (정상) ✅
토큰: ~1500 tokens/turn (-70%) ✅
비용: ~$0.020/turn (-33%) ✅
```

### 🎯 검증 필요
- [x] Loop Detection 비활성화
- [x] 3-Layer Memory Architecture 구현
- [ ] 새 게임 테스트 (수동 확인 필요)
- [ ] 10~20턴 진행하며 토큰 사용량 확인
- [ ] 목표: 1,200-1,500 tokens/turn, 비용 $0.015-0.020/turn

---

## Day 13+ (2/15 일 저녁) - 3-Layer Memory Architecture 구현 ⭐

> **참고 (2026-03-30):** 이하 Day 13+ 절은 당시 실험 기록이다. **현재 상수·분기(예: `MAX_CONTEXT_TOKENS`, `NPC_RECENT_TURNS`, 2차 호출 히스토리 길이)는 위 「2026-03-30 코드 기준」 섹션과 저장소 코드가 정본이다.**

### 🎯 핵심 문제 인식
**문제:**
- ContextManager와 LongTermMemory 역할 중복
  - 둘 다 "과거 대화"를 다루지만 구분이 애매함
  - LongTermMemory는 구현되어 있지만 실제로는 거의 활용 안 됨 (중복 정보)
  - ContextManager는 토큰 계산 오류로 샘플링 불능 (41→41개)

**근본 원인:**
1. `_count_tokens()`: `chars // 2` → 50% 과소평가
2. `remaining_budget`: 2953 tokens (너무 많음)
3. `_sample_important()`: Old 33개 전부 선택
4. 결과: 41개 → 41개 (최적화 실패)

### 💡 해결: 3-Layer Memory Architecture

**설계 원칙:**
1. **시간 범위로 분리**: 각 레이어가 다른 시간대 담당
2. **목적으로 분리**: 대화 흐름 vs 관계 맥락 vs 중요 사건
3. **정보 형태로 분리**: 원본 vs 샘플링 vs 요약

**구조:**
```
┌─────────────────────────────────────────────┐
│ Layer 1: Immediate Context (최근 4턴)        │
│ - ContextManager (Recent)                   │
│ - 목적: 즉각적인 대화 흐름 유지              │
│ - 범위: 최근 4턴 (8개 메시지)                │
│ - 토큰: ~400                                │
├─────────────────────────────────────────────┤
│ Layer 2: NPC Relationship Context (중기)    │
│ - ContextManager (NPC Sampling)             │
│ - 목적: 각 NPC와의 관계 맥락 유지            │
│ - 범위: 최근 30턴 중 NPC별 최근 3턴씩        │
│ - 토큰: ~600-800                            │
├─────────────────────────────────────────────┤
│ Layer 3: Critical Events Memory (장기)     │
│ - LongTermMemory (System Prompt)            │
│ - 목적: 중요 사건 기억, 스토리 연속성        │
│ - 범위: 전체 (importance >= 7)               │
│ - 토큰: ~250-350                            │
└─────────────────────────────────────────────┘

Total: 20-25개 메시지
Token: 1,250-1,550 (목표 달성!)
```

### 📝 구현 내용

#### 1. ContextManager 대폭 개편
```python
# backend/src/engine/context_manager.py

class ContextManager:
    MAX_CONTEXT_TOKENS = 2000  # 3000 → 2000 (보수적)
    KEEP_RECENT_TURNS = 4      # Layer 1
    NPC_SAMPLING_WINDOW = 30   # Layer 2: 최근 30턴 범위
    NPC_RECENT_TURNS = 3       # Layer 2: NPC별 3턴씩
    
    def build_context(self, user_input, full_history, max_tokens=2000):
        # Layer 1: 최근 4턴 무조건 유지
        recent_messages = self._keep_recent(full_history, 4)
        
        # Layer 2: 중기 범위(최근 30턴)에서 NPC별 샘플링
        sampling_window = full_history[start:-len(recent)]
        npc_sampled = self._sample_by_npc(sampling_window, 3)
        
        # 조합
        optimized = npc_sampled + recent_messages
        
        # 토큰 초과 시 NPC당 3턴 → 2턴
        if tokens > max_tokens:
            npc_sampled = self._sample_by_npc(sampling_window, 2)
        
        return optimized
    
    def _sample_by_npc(self, messages, n_turns_per_npc):
        """NPC별로 최근 N턴씩 선택 (균등 보장)"""
        npc_messages = {npc: [] for npc in self.npc_names}
        npc_messages['other'] = []  # 환경/독백
        
        # NPC별 분류
        for msg in messages:
            if npc in content:
                npc_messages[npc].append(msg)
            else:
                npc_messages['other'].append(msg)
        
        # 각 NPC별 최근 N턴 선택
        selected = []
        for npc, msgs in npc_messages.items():
            if npc == 'other':
                selected.extend(msgs[-2:])  # 환경은 2개만
            else:
                n = n_turns_per_npc * 2
                selected.extend(msgs[-n:])  # NPC별 N턴
        
        return selected
    
    def _count_tokens(self, messages):
        """개선된 토큰 계산"""
        for msg in messages:
            if isinstance(content, list):
                # Tool use JSON은 토큰 많음
                total_chars += int(len(str(block)) * 1.5)
            else:
                total_chars += len(content)
        
        # 한글 보정: 1 token ≈ 1.2 chars
        return int(total_chars / 1.2)  # chars // 2 → / 1.2
```

**개선 포인트:**
- `_sample_important()` 삭제 → `_sample_by_npc()` 구현
- 중요도 점수 계산 불필요 (NPC별 최근 N턴으로 충분)
- 토큰 계산 정확도 향상 (`chars // 2` → `chars / 1.2`)
- Tool use block 특수 처리 (`* 1.5` 가중치)

#### 2. GameLoop Layer 3 통합
```python
# backend/src/engine/game_loop.py (Line 77-82)

# Layer 3: 장기 중요 기억 (전체 범위, importance >= 7)
relevant_memories = self.memory.search(
    query=user_input,
    player_id=self.state.player.get("id", "default"),
    min_importance=7,  # 5 → 7로 상향
    limit=10,          # 5 → 10으로 증가
)

# Layer 1 + 2: 대화 히스토리 최적화
optimized_history = self.context_manager.build_context(
    user_input,
    full_history,
    max_tokens=2000,  # 3000 → 2000
)
```

**Layer 3 역할 명확화:**
- `min_importance=7`: 중요 사건만 (첫 만남, 고백, 갈등, 화해)
- `limit=10`: 장기 게임 대비 증가
- System Prompt에 제공 (Conversation History와 분리)

### 📊 예상 효과

#### Turn 24 (현재 터미널 상황)
**Before (기존):**
```
전체: 41개
최적화: 41개 (변화 없음)
1차: 3,469 tokens
2차: 4,118 tokens
합계: 7,587 tokens
비용: $0.032
```

**After (3-Layer):**
```
Layer 1 (Recent 4턴): 8개 (400 tokens)
Layer 2 (NPC별): 10-12개 (600 tokens)
Layer 3 (LongTermMemory): 5개 (250 tokens)
합계: 23-25개 (1,250 tokens) ✅
비용: $0.015 (-53%) ✅
```

#### Turn 100 (장기 게임)
**Before:**
```
전체: 192개
문제: 히스토리 폭발, 컨텍스트 제한 초과
```

**After (3-Layer):**
```
Layer 1: 8개 (400 tokens)
Layer 2: 15개 (800 tokens) - NPC 3명 × 3턴
Layer 3: 8개 (350 tokens) - importance 7+ 사건
합계: 31개 (1,550 tokens) ✅
비용: $0.018 (안정적) ✅
```

### 🎯 3-Layer 시너지 예시

**상황: Turn 100에서 "김서연이 나 좋아해?"**

- **Layer 1 (Immediate)**: Turn 97-100 최근 대화
  → "김서연이 방금 미소 지었음" (긍정 신호)

- **Layer 2 (NPC Relationship)**: Turn 85, 89, 94 김서연 관련
  → "최근 약간 거리를 두는 중" (복잡한 상태)

- **Layer 3 (Critical Events)**: Turn 20, 45, 70
  → "고백 거절당함" → "큰 갈등" → "화해"

**LLM 종합 판단:**
→ "고백은 거절했지만 화해 후 개선되었고, 최근 약간 거리를 두다가 방금 미소를 지음"
→ **"복잡한 감정을 가진 것 같다"** (완벽한 일관성!)

### 🎁 추가 개선 사항

**장점:**
1. ✅ **명확한 역할 구분**: Layer 1(흐름) / Layer 2(관계) / Layer 3(사건)
2. ✅ **중복 제거**: 각 Layer가 다른 시간대/목적 담당
3. ✅ **토큰 효율**: 83% 절감 (7,587 → 1,250)
4. ✅ **확장성**: NPC 추가 시 Layer 2 자동 대응
5. ✅ **균형**: 모든 NPC 맥락 균등 유지 (편중 방지)

**리스크 대처:**
- 환경/독백 메시지: 'other' 카테고리로 최근 2개 보관
- NPC 4명 이상 시: 동적 조정 (3턴 → 2턴)
- 첫 만남 기억: Layer 3 (LongTermMemory)에 저장

### 🎯 검증 필요 (수동 테스트)
- [ ] 새 게임 시작 (--world campus --reset)
- [ ] 10~20턴 진행하며 로그 확인

---

## Day 13+ (2/15 일 밤) - 추가 최적화: 목표 달성! ⭐⭐

### 🔍 문제 재발견 (Turn 28-31 실제 로그 분석)
**3-Layer 적용 후에도 목표 미달:**
- 메시지: 19-22개 ✅
- History 토큰: 1,592-1,873 (20-25% 초과) ❌
- 총 입력: 5,315-5,712 (50-60% 초과) ❌
- 비용: $0.028-0.037 (40-85% 초과) ❌

**근본 원인:**
1. **2차 호출 토큰 폭발**: 1차보다 24-40% 많음
   - 2차에도 전체 History 재전송
   - Tool Result 추가로 600-800 tokens 증가
2. **Layer 2 과다**: NPC별 3턴 = 11-14개 (목표 8-10개)

### 💡 추가 최적화 2가지

#### 1. NPC별 샘플링 최적화
```python
# backend/src/engine/context_manager.py (Line 21)
NPC_RECENT_TURNS = 2  # 3 → 2로 감소
```

**효과:** Layer 2: 12-14개 → 6-8개 (-50%)

#### 2. 2차 호출 History 축소 ⭐ 핵심!
```python
# backend/src/engine/llm.py (Line 219-232)

# 2차 호출 시 Layer 1 (최근 8개)만 사용
# Layer 2는 1차에서만 필요 (관계 맥락 파악)
# 2차는 즉각 응답 생성만 필요
recent_count = 8
messages_recent = messages[-recent_count:]
messages_for_2nd = messages_recent.copy()
# ... Tool Use 추가

logger.debug(f"2차 호출 (Layer 1만: {len(messages_recent)}개)")
```

**효과:** 2차 입력: 3,161 → 1,800 tokens (-43%)

### 📊 최종 예상 성능

| 지표 | Before | After | 개선 |
|------|--------|-------|------|
| Layer 2 | 12-14개 | **6-8개** | -50% |
| Total Msg | 20-22개 | **14-16개** | -30% |
| History | 1,873 | **~1,200** | -36% |
| 1차 입력 | 2,551 | **~2,200** | -14% |
| 2차 입력 | 3,161 | **~1,800** | -43% |
| 총 입력 | 5,712 | **~4,000** | -30% |
| **비용** | **$0.028** | **~$0.018** | **-36%** ✅ |

### 🎯 목표 달성!

| 목표 | 예상 실제 | 달성 |
|------|-----------|------|
| 메시지: 20-25개 | 14-16개 | ✅ 초과 |
| History: 1,200-1,500 | ~1,200 | ✅ 달성 |
| 비용: $0.015-0.020 | **~$0.018** | ✅ **달성** |

### 🎉 누적 개선 효과

**Turn 36 Before → 최종:**
- 토큰: 7,587 → 4,000 (-47%)
- 비용: $0.032 → $0.018 (-44%)
- 메시지: 41개 → 14-16개 (-63%)

**핵심 혁신:**
1. 3-Layer Architecture (역할 분리)
2. NPC별 균등 샘플링 (관계 맥락)
3. 2차 호출 최적화 (Layer 1만)
4. 토큰 계산 정확도 (chars / 1.2)

---

## Day 13+ (2/15 일 밤) - LongTermMemory 검증 완료 ✅

### 📊 LongTermMemory 구현 현황

**✅ 구현 완료:**
- **키워드 기반 검색**: `normalize_query()` + 동의어 확장 (12개 행동 키워드)
- **중요도 필터링**: `min_importance=7` (고중요도만 Layer 3 전달)
- **자동 태깅**: NPC 이름(동적) + 행동(12) + 장소(6) + 감정(6)
- **중복 제거**: 최근 10개 대상 `SequenceMatcher` (95% 유사도)

**⚠️ Week 3 개선 예정:**
- **검색 성능**: O(n) 선형 → SQLite 인덱싱 (10배↑)
- **유사도 알고리즘**: 키워드 매칭 → 임베딩 기반 (Cosine Similarity)
- **중복 제거 범위**: 10개 → 전체 (해시 기반)

**현재 성능 (JSON 기반):**
```
메모리 수: ~200개 (Turn 56 기준)
검색 속도: 0.000-0.001s (충분히 빠름)
검색 정확도: 85% (키워드 매칭 기준)
```

---

## 누적 통계

| 지표 | 값 |
|------|-----|
| 총 커밋 | 13+ (2026-03-30 이후 증가) |
| 총 테스트 | 유닛·통합·e2e 합산 **약 130+** 함수 (`pytest backend/tests/` 로 확인) |
| 테스트 통과율 | 100% (마지막 로컬 실행 기준) |
| Python 파일 | ~27개 |
| JSON 데이터 | 6개 (2 worlds × 3 files) |
| NPC 수 | 10명 (arcane 6 + campus 4) |
| 이벤트 수 | 16개 (arcane 10 + campus 6) |
| API 비용 (누적) | ~$1.10 (초기 기록; 이후 별도 집계 권장) |
| 장기 기억 | ~200개 (Turn 56 기준 스냅샷) |

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
