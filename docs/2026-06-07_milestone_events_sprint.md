# 마일스톤 이벤트 스프린트 (2026-06-06 ~ 07)

| 항목 | 내용 |
|------|------|
| 상태 | **Day 1~2 완료** (플레이·에디터·민근이 시드 검증) |
| 정본 링크 | [`STAT_DRIVEN_EVENTS.md`](STAT_DRIVEN_EVENTS.md) · 본 문서 |
| 샘플 데이터 | [`scripts/hipstar_milestone_events.json`](../scripts/hipstar_milestone_events.json) |

---

## 1. 목표 (달성)

**「관계 임계 → 능력 점프 → NPC 다음 턴 인지」** 루프를 베타 전에 완성.

| 방식 | 설명 |
|------|------|
| **A** | 정적 EventCard (제목·설명·스탯 before→after) |
| **B** | `narrative_hint` → 다음 턴 dynamic 프롬프트 1회 주입 후 클리어 |
| **C** | 미니 LLM 이벤트 생성 — **v2 보류** |

추가 LLM 호출 없음. 발동·효과는 **백엔드 결정론**.

---

## 2. 완료 항목

### 백엔드

| 항목 | 파일·요약 |
|------|-----------|
| `npc_id` 관계 조건 | `events.py` — 선택 시 해당 NPC만, 없으면 any-NPC (하위 호환) |
| `once` + `triggered_events` | 동일 ID 재발동 스킵 |
| `applied_effects` API | `event_response.py`, `play.py` — `delta`, `label_ko`, `before`/`after` |
| `narrative_hint` 큐 | `game_loop.py` — `pending_event_hints`, `for_turn` TTL, 턴당 최대 1개 주입 |
| payload 영속화 | `play_persistence.py` — `pending_event_hints` JSON 필드 |
| `events` API 타입 | `worlds.py` — `list \| dict \| null` (배열 시드 500 수정) |
| 나레이션 카드 상한 | `dialogue_split.py` — 내레이션 블록 합치기, 최대 6카드 |
| 프롬프트 | `prompt_optimizer.py` — 블록 5개·내레이션 1개, dynamic 「이번 턴 출력 제한」 |

### 프론트

| 항목 | 파일 |
|------|------|
| EventCard 모달 | `EventCard.tsx` — 순차 큐, 긍정/부정 색 |
| PlayPage 통합 | `PlayPage.tsx` — `[이벤트]` 채팅 줄 제거 |
| 월드 에디터 이벤트 | `WorldEventsEditor.tsx`, `worldEditorEvents.ts` |
| 플레이어 스탯 정의 | 간편 모드 → `stats_schema.resource` |
| 관계 스탯 NPC별 | `NpcRelationshipStatsEditor.tsx` |

### 데이터·검증

- 민근이 월드 (`8f02a43b-...`) `events_data` 7개 시드
- 실플레이: 호감·로맨스·rap 마일스톤 발동, EventCard·스탯 변경 확인
- 유닛 테스트: `test_events`, `test_event_response`, `test_game_engine_events`, `test_dialogue_split`, `test_prompt_optimizer` 등

---

## 3. 아키텍처 요약

```
[월드 events_data] ──세션 시작──► EventManager
         │
[턴] LLM → relationship_changes (관계만)
         → advance_turn
         → check_events(snapshot)  ← 관계·스탯·compound 조건
         → apply_effects           ← resource_stat (LLM 아님)
         → queue narrative_hint
         → events_triggered → API → EventCard

[다음 턴] consume pending_hint → dynamic 「방금 일어난 일」
```

**LLM이 하지 않는 것 (현재):** 이벤트 정의, 발동 판정, 자원 스탯 효과 적용.

---

## 4. 내일 할 일 (2026-06-08)

### 4-1. 복합 관계 조건 (감정 2개 이상)

**목표:** 한 NPC에 대해 `affection >= 40 AND romance >= 30` 같은 **다중 관계 스탯** 마일스톤.

| # | 작업 | 산출물 |
|---|------|--------|
| 1 | `compound` + `relationship_threshold` × N 지원 확인·보강 | `events.py` (이미 `compound` 있음 — 에디터·문서 정합) |
| 2 | 월드 에디터: 「복합(AND)」에 **관계 2줄** UI (같은 `npc_id`) | `WorldEventsEditor.tsx` |
| 3 | 직렬화: `conditions: [rel₁, rel₂]` 또는 `rel + resource` | `worldEditorEvents.ts` |
| 4 | 민근이 샘플 1개 추가 (예: affection≥50 AND romance≥40) | `events_data` |
| 5 | 단위 테스트 3~5개 | `test_events.py` |

**JSON 예시:**

```json
{
  "condition": {
    "type": "compound",
    "op": "and",
    "conditions": [
      { "type": "relationship_threshold", "npc_id": "world_xxx", "stat": "affection", "op": ">=", "value": 50 },
      { "type": "relationship_threshold", "npc_id": "world_xxx", "stat": "romance", "op": ">=", "value": 40 }
    ]
  }
}
```

### 4-2. LLM 자원 스탯 + EventCard (설계 → 구현)

**방향 (합의안):** 마일스톤(작가) + LLM 미세 조정(상황), **동일 EventCard API**.

| # | 작업 | 상세 |
|---|------|------|
| 1 | `update_game_state`에 `resource_stat_changes[]` 추가 | `llm.py` input_schema |
| 2 | `validator` + `state.apply_changes` | `stats_schema` 키만, clamp, 턴당 ±N 캡 |
| 3 | 턴 종료 시 **합성 `events_triggered`** | `game_loop.py` — `event_id: llm_stat_*`, `applied_effects` 동일 형태 |
| 4 | 카드 노출 정책 | `|change| >= 3` 또는 `show_card: true` (매 턴 +1 카드 방지) |
| 5 | 프롬프트 가이드 | 의미 있는 순간만; 마일스톤과 중복 인플레 방지 |
| 6 | 테스트 | validator, apply_changes, API 직렬화 |

**합성 응답 예:**

```json
{
  "event_id": "llm_stat_turn_42",
  "name": "실력 변화",
  "description": "새벽 연습이 몸에 배었다.",
  "applied_effects": [{ "type": "resource_stat", "key": "rap", "delta": 2, "before": 28, "after": 30, "label_ko": "랩" }]
}
```

**선택:** `narrative_hint` — LLM `reason`을 다음 턴에 넣을지, 마일스톤만 넣을지 정책 결정.

### 4-3. 최종 마무리 (베타 전)

| # | 작업 |
|---|------|
| 1 | 관계 프롬프트 보수화 (「매 턴」→ 의미 있을 때만) — 밸런스 |
| 2 | E2E 시나리오 문서화 또는 스크립트 (호감 40 돌파 → 카드 → 다음 턴 힌트) |
| 3 | `STAT_DRIVEN_EVENTS.md` §9 갱신 → 본 스프린트 결과 반영 |
| 4 | Docker 재배포 체크리스트 한 줄 (`build api web`) |

---

## 5. 요건 정리 (Requirements)

### 기능 요건 (완료)

| ID | 요건 | 상태 |
|----|------|------|
| E-01 | `relationship_threshold`에 선택적 `npc_id` | ✅ |
| E-02 | `once` 이벤트 1회 발동 | ✅ |
| E-03 | 턴 응답에 `applied_effects` + 한글 라벨 | ✅ |
| E-04 | `narrative_hint` 다음 턴 1회 주입·클리어 | ✅ |
| E-05 | EventCard UI (순차, 스탯 표시) | ✅ |
| E-06 | 월드 에디터 간편 이벤트·스탯 정의 | ✅ |
| E-07 | `events_data` 배열·객체 API 호환 | ✅ |
| E-08 | 나레이션 블록 UI 상한 (후처리) | ✅ |

### 기능 요건 (예정)

| ID | 요건 | 우선순위 |
|----|------|----------|
| E-09 | 동일 NPC **관계 스탯 2개 이상** AND 조건 (에디터+엔진) | P0 |
| E-10 | LLM `resource_stat_changes` + 동일 EventCard | P0 |
| E-11 | LLM 스탯 변화 턴당 캡·카드 표시 임계값 | P1 |
| E-12 | 복합 조건 에디터 UX (관계+관계, 관계+스탯) | P1 |
| E-13 | E2E 회귀 시나리오 자동화 | P2 |

### 비기능 요건

| ID | 요건 |
|----|------|
| NF-01 | 마일스톤 발동에 **추가 LLM 호출 없음** |
| NF-02 | 기존 세션 payload 하위 호환 (`pending_event_hints` 기본 `[]`) |
| NF-03 | 이벤트 효과는 `stats_schema.resource` clamp |
| NF-04 | 턴당 마일스톤 발동 `max_events_per_turn` (기본 1) |

### 제약 (유지)

- 관계 스탯 효과는 이벤트 `apply_effects`로 넣지 않음 — LLM `relationship_changes`만.
- 자원 스탯 마일스톤 점프는 **작가 정의 이벤트** (현재). LLM 스탯은 E-10에서 별도 경로.

---

## 6. 운영 메모

- **새 세션**으로 플레이해야 `events_data` 로드됨.
- 코드 반영: `docker compose build api web && docker compose up -d api web`
- PWA 캐시: 시크릿 창 또는 Cmd+Shift+R

---

## 7. 변경 로그

- **2026-06-07** — Day 1~2 완료, 본 문서·요건·내일 할 일 정리.
