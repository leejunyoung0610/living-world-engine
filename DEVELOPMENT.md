# Living World Engine - 개발 일지

> 4주 개발 과정을 기록하는 문서
> 시작일: 2025-02-15 (토) / 마감일: 2025-03-15 (토)

---

## 진행 현황

| 주차 | 목표 | 상태 | 테스트 |
|------|------|------|--------|
| **Week 1** (2/15~2/21) | 핵심 엔진 + LLM 통합 | 🔴 진행중 | 53/53 pass |
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

### Day 2 (2/16 일) ⬜

**예정:**
- [ ] WorldState.load_from_file로 세계관 JSON 실제 로딩 테스트
- [ ] GameEngine.process_turn 통합 테스트 (실제 Claude API 1턴 플레이)
- [ ] 시스템 프롬프트 튜닝 (NPC 성격 반영)
- [ ] 대화 히스토리 관리 개선

---

### Day 3-4 ⬜

**예정:**
- [ ] WorldState 고도화 (퀘스트 시스템, 인벤토리)
- [ ] KeywordMemorySearch 고도화 (NPC별 기억 분리)
- [ ] 유닛 테스트 추가

---

### Day 5-7 ⬜

**예정:**
- [ ] ClaudeClient 고도화 (에러 재시도, 토큰 관리)
- [ ] 통합 테스트 (LLM + 상태 변경 + 메모리)
- [ ] 10턴 연속 플레이 테스트

---

## Week 2: 이벤트 & 루프 방지

### Day 8-10 ⬜
- [ ] EventManager 완성 (조건 평가, 이벤트 트리거)
- [ ] 이벤트 시스템 테스트

### Day 11-12 ⬜
- [ ] LoopDetector 고도화 (강제 이벤트 주입)
- [ ] 루프 방지 테스트

### Day 13-14 ⬜
- [ ] GameEngine 전체 통합
- [ ] E2E 테스트 (10턴 플레이)

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

## 누적 통계

| 지표 | 값 |
|------|-----|
| 총 커밋 | 1 |
| 총 테스트 | 53 |
| 테스트 통과율 | 100% |
| Python 파일 | ~20개 |
| JSON 데이터 | 3개 (world, characters, events) |
| NPC 수 | 6명 |
| 이벤트 수 | 10개 |
| API 비용 (누적) | ~$0.02 |

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
