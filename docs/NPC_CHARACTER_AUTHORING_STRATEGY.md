# NPC 캐릭터 저작 전략 — 3계층 · 3-Way 입력

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-05-27 |
| 상태 | **전략 정본** (구현 전) |
| 목적 | UGC 작성자는 폼·자연어만 쓰고, 시스템이 구조(JSON)와 LLM 프롬프트를 관리한다 |
| 관련 문서 | [`WORLD_VISUAL_AI_ROADMAP.md`](WORLD_VISUAL_AI_ROADMAP.md) · [`STAT_DRIVEN_EVENTS.md`](STAT_DRIVEN_EVENTS.md) §0 · [`DEVELOPMENT.md`](../DEVELOPMENT.md) · [`2026-05-27_npc_authoring_strategy.md`](2026-05-27_npc_authoring_strategy.md) |
| 관련 코드 | `frontend/src/utils/worldEditorSimple.ts` · `frontend/src/pages/WorldEditorPage.tsx` · `backend/src/api/routes/worlds.py` · `backend/src/engine/prompt_optimizer.py` · `backend/src/services/image_generator.py` |

---

## 1. 판단 요약

### 질문: “텍스트만 썼을 때 DB·스키마로 자동 저장 — 어렵나?”

**어렵지 않다.** 이미 **레이어 2(저장)** 와 **레이어 3(실행)** 의 뼈대는 있다.

| 계층 | 오늘 | 갭 |
|------|------|-----|
| **L1 사용자 입력** | 간편 폼 + JSON 모드 | LLM용 필드(전공·성격·배경) 폼 부재, 자유 텍스트→구조 AI 없음 |
| **L2 저장** | `World.characters_data` JSON (`npcs[]`) | **공식 NPC 스키마·검증 없음** — 필드가 관례에 의존 |
| **L3 실행** | `SystemPromptOptimizer`가 턴별 NPC 서브셋 + 컴팩트 프로필 | `background` 등 일부 필드 **프롬프트 미반영**, 키 불일치(`speech_style` vs `speaking_style`) |

따라서 **새 아키텍처를 짓는 작업이 아니라**, L1을 채우고 L2 스키마를 명문화한 뒤 L3 소비처를 맞추는 **순차 보강**이 맞다.

### 핵심 원칙 (합의)

- ❌ 유저에게 JSON 작성을 **요구하지 않는다**
- ✅ **시스템**이 구조(`characters_data`)를 소유·검증한다
- ✅ 유저는 **폼** 또는 **자연어(+ AI 정리·검수)** 로 입력한다
- ✅ **고급 JSON 편집**은 토글로 유지 (이미 구현됨)

---

## 2. 3계층 아키텍처

```mermaid
flowchart TB
  subgraph L1["레이어 1 — 사용자 입력 (UI)"]
    F[폼 / 마법사]
    T[자유 설명 + AI 정리]
    J[JSON 고급 모드]
  end

  subgraph L2["레이어 2 — 저장 (DB)"]
    DB[(World.characters_data<br/>npcs[] 구조화 JSON)]
  end

  subgraph L3["레이어 3 — 실행 (Prompt)"]
    PO[SystemPromptOptimizer]
    IG[image_generator]
    PUB[공개 brief API]
  end

  F --> DB
  T -->|검수 후| DB
  J --> DB
  DB --> PO
  DB --> IG
  DB --> PUB
```

### 레이어 1 — 사용자 입력

- JSON을 **기본 UI에 노출하지 않음**
- 입력 방식 3가지 (**3-Way**, 아래 §3)
- 각 필드에 **도움말**: “이 값이 NPC 대화·초상에 어떻게 쓰이는지”

### 레이어 2 — 저장

- 단일 진실 출처: PostgreSQL `worlds.characters_data` (JSON 컬럼)
- UGC 월드는 **`npcs`만 저장** (`player`는 플레이 시작 시 합성 — [`STAT_DRIVEN_EVENTS.md`](STAT_DRIVEN_EVENTS.md) §0)
- **정본 스키마**는 §4 — API 저장 시 검증(Pydantic), 프론트는 동일 타입 공유

### 레이어 3 — 실행

- **대화 LLM**: `prompt_optimizer.build_system_blocks` → `_format_compact_npcs` + `dialogue_npc_cap` 선택
- **초상 AI**: `appearance_for_ai` 우선, 없으면 personality/background 등 fallback
- **공개 카드**: `_public_npc_briefs` — name, role(+major 병합), summary, portrait

**레이어 2와 3의 계약:** 저장 스키마에 있는 필드는 §5 매트릭스대로 **반드시** 소비처에 반영되거나, 의도적으로 “저장만·미사용”으로 문서화한다.

---

## 3. 3-Way 입력 전략

| 방식 | 대상 | 안정성 | 구현 상태 |
|------|------|--------|-----------|
| **A. 폼 입력** | ~95% | ★★★★★ | **부분** — id/name/role/appearance_for_ai/초상만 |
| **B. 자유 텍스트 + AI 정리** | ~5% | ★★★★ (검수 필수) | **미구현** |
| **C. JSON 직접 편집** | 고급 | ★★★ (스키마 숙지 필요) | **있음** — `WorldEditorPage` json 모드 |

### A. 폼 입력 (추천 기본)

NPC 추가 화면에서 **방법 선택** UI:

```
◉ 폼으로 입력 (추천)
○ 자유 설명으로 (AI가 정리)
○ JSON 직접 편집 (고급)
```

**Phase A에서 추가할 필드** (§4 Canonical NPC):

| 필드 | 필수 | UI 라벨 | 도움말 예 |
|------|------|---------|-----------|
| `name` | ✓ | 이름 | 대화에 표시되는 이름 |
| `role` | ✓ | 역할 | 친구, 선배, 교수님 |
| `major` | | 전공·직업 | 학교 배경일 때. 대화에서 자기소개에 쓰임 |
| `personality` | | 성격 | 짧게: "차분하고 책임감 강함" |
| `background` | | 배경 (선택) | 추가 설정·과거 사건 |
| `speaking_style` | | 말투 (선택) | 존댓말/반말, 톤 |
| `appearance_for_ai` | | 외모·복장 (초상용) | **대화 LLM에는 넣지 않음** — 초상 AI 전용 |
| `portrait_image_url` | | (미리보기) | AI 생성 또는 URL |

**의도적으로 폼에서 빼는 것 (당분간):** `location` — 대화세계에서 장소 기반 NPC 필터는 제거됨 ([`DEVELOPMENT.md`](../DEVELOPMENT.md) dialogue_npc_cap). JSON 레거시는 import 시 보존만.

### B. 자유 텍스트 + AI 정리

**흐름:**

1. 유저: `"20살 경영학과 여자, 차분한 성격. 도서관에 자주 있음."`
2. 클라이언트 → `POST /api/worlds/…/npcs/parse-draft` (또는 월드 무관 `POST /api/npc/structure-draft`)
3. 서버: Claude **구조화 출력** (JSON Schema / tool_use)
4. 클라이언트: **폼에 채워진 초안** 표시 → 유저 검수·수정 → 저장

**반드시 지킬 것:**

- AI 결과는 **저장 전 사람이 확인** (자동 저장 금지)
- 파싱 실패 시 폼 모드로 fallback
- 비용: BYOK·일 턴과 별도 **저작 API 쿼터** 또는 “월드 저장 시에만” 제한 검토

**난이도:** 중 — 엔진 `llm.py` 패턴 재사용 + Pydantic 검증 1엔드포인트 + 폼 prefill UI.

### C. JSON 고급 모드

- 현재 `WorldEditorPage` **유지**
- 간편↔JSON **라운드트립** 시 §4 필드 **손실 없음** (이미 extra 필드는 JSON에 남음)
- 고급 모드 도움말에 **§4 Canonical 스키마** 링크

---

## 4. Canonical NPC 스키마 (UGC 정본)

저장 단위: `characters_data.npcs[]` 각 항목.

### 4-1. 필수

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | `[a-z0-9_-]+`, 월드 내 유일 |
| `name` | string | 표시 이름 |
| `role` | string | 관계·직함 한 줄 |

### 4-2. LLM 대화 (L3 — prompt_optimizer)

| 필드 | 타입 | 비고 |
|------|------|------|
| `major` | string? | 전공·직업 — **자기소개 일관성용** |
| `personality` | string? | 성격 한 줄~단락 |
| `background` | string? | LLM 대화 — 컴팩트 프로필에 반영 (200자 cap) |
| `speaking_style` | string \| object? | 문자열 우선; 객체는 formality/mood 등 |
| `persona` | object? | `traits[]`, `drive` — 템플릿 월드용 |
| `skills` | string[]? | |
| `interests` | string[]? | |

**통일 규칙:** `speech_style`(arcane 템플릿) → **`speaking_style`로 읽기 호환** (마이그레이션·import 시 alias).

### 4-3. 비주얼 (L3 — image_generator, 공개 UI)

| 필드 | 타입 | 비고 |
|------|------|------|
| `appearance_for_ai` | string? | 초상 프롬프트 1순위 |
| `portrait_image_url` | string (HTTPS)? | R2 미러 URL 권장 |

### 4-4. 레거시·보류

| 필드 | 처리 |
|------|------|
| `location` | 저장·import 보존, **대화 선택/프롬프트 미사용** |
| `initial_stats` | Phase 2+ — 플레이 시작 시 `relationships` 시드 |
| `age` | 선택, brief·프롬프트에 넣을지 Phase A에서 결정 |
| `description` | `background`와 동의어로 import 시 병합 |

### 4-5. 코드 위치 (구현 시)

| 레이어 | 신규/수정 |
|--------|-----------|
| L2 검증 | `backend/src/schemas/npc.py` (Pydantic `NpcRecord`, `CharactersPayload`) |
| L2 API | `worlds.py` — create/update 시 `NpcRecord` 검증 |
| L1 타입 | `frontend/src/types/npc.ts` |
| L1 폼 | `worldEditorSimple.ts` — `SimpleNpcRow` 확장 |
| L3 | `prompt_optimizer._format_compact_npcs` — `background`, alias 통일 |

---

## 5. 필드 소비 매트릭스 (현재 → 목표)

| 필드 | 간편 폼 | DB 저장 | LLM 프롬프트 | 초상 AI | 공개 brief |
|------|---------|---------|--------------|---------|------------|
| id, name, role | ✓ | ✓ | ✓ | name | ✓ |
| major | ✓ | ✓ | ✓ | ✗ | role에 병합 |
| personality | ✓ | ✓ | ✓ | fallback | summary |
| background | ✓ | ✓ | ✓ | fallback | summary |
| speaking_style | ✓ | ✓ | ✓ (`speech_style` alias) | ✗ | ✗ |
| appearance_for_ai | ✓ | ✓ | ✗ (의도) | ✓ 1순위 | ✗ |
| portrait_image_url | ✓ | ✓ | ✗ | ✗ | portrait_url |
| location | import만 | ✓ | ✗ | ✗ | ✓ |
| persona, skills, interests | JSON만 | ✓ | ✓ | ✗ | ✗ |

**버그 클래스로 간주:** 폼/AI로 `major: "무용과"`를 저장했는데 LLM이 다른 과로 말함 → §5에서 LLM 열이 ✓인지, **모순되는 `background`/`role` 텍스트**가 없는지 확인.

---

## 6. 개발 로드맵

### Phase A — 폼 강화 (간편 모드) ⭐ 먼저

**상태 (2026-05-27):** ✅ 반영 — 간편 폼 `major`/`personality`/`background`/`speakingStyle`, `prompt_optimizer` background·`speech_style` alias, `backend/src/schemas/npc.py` 저장 정규화.

**목표:** JSON 없이도 대화 품질에 필요한 필드를 채울 수 있다.

| 작업 | 상세 |
|------|------|
| A1 | `SimpleNpcRow` + 폼 UI: major, personality, background, speaking_style |
| A2 | `formToWorldPayload` / `tryImportSimpleFromJson` — 새 필드 직렬화·역직렬화 |
| A3 | 필드별 도움말 + “대화/초상에 쓰이는 곳” 툴팁 |
| A4 | `prompt_optimizer`: `background` 1줄 추가, `speech_style` → `speaking_style` alias |
| A5 | (선택) Pydantic `NpcRecord` — 저장 시 최소 검증 (id/name/role) |

**DoD:** 캠퍼스 샘플 수준 NPC를 **폼만으로** 만들고, 플레이 시 `major`·`personality`가 프롬프트에 보인다.

**예상 규모:** 프론트 1~2일 + 백엔드 프롬프트 0.5일 + 테스트.

### Phase B — 자유 텍스트 → 구조화 AI

**목표:** 한 문단 입력 → 폼 prefill → 검수 → 저장.

| 작업 | 상세 |
|------|------|
| B1 | `POST /api/worlds/npc-structure-draft` — body: `{ "text": "…" }`, response: `NpcRecord` 초안 |
| B2 | Claude structured output + Pydantic 검증 + 실패 422 |
| B3 | 에디터 “✨ AI로 정리하기” → 폼 채움, **저장은 유저 클릭** |
| B4 | 단위 테스트: 고정 mock LLM, 파싱·검증 |

**DoD:** 예시 문장 3개가 기대 필드로 파싱되고, 유저가 수정 후 PUT 성공.

**예상 규모:** 2~3일 (쿼터·비용 정책 포함).

### Phase C — 고급 JSON 모드 유지

| 작업 | 상세 |
|------|------|
| C1 | JSON 모드 도움말에 §4 스키마 링크 |
| C2 | JSON → 간편 import 시 새 필드 매핑 (Phase A 필드) |
| C3 | 스키마 위반 시 PUT 422 메시지 개선 |

**이미 있음:** 토글, textarea, `tryImportSimpleFromJson` 실패 시 json 강제.

---

## 7. UX 와이어 (NPC 추가)

```
┌────────────────────────────────────────┐
│  새 NPC 추가                            │
├────────────────────────────────────────┤
│  방법: ◉ 폼  ○ AI 정리  ○ JSON 고급     │
│                                        │
│  이름 *     [______________]           │
│  역할 *     [______________]  💡 선배…  │
│  전공       [______________]  💡 대화용   │
│  성격       [______________]  💡 짧게    │
│  배경       [______________]  💡 선택    │
│  말투       [______________]  💡 선택    │
│  ── 초상 (비주얼) ──                    │
│  외모·복장  [______________]  💡 AI만    │
│  [✨ AI 초상 생성]                      │
└────────────────────────────────────────┘
```

자유 설명 모드 선택 시:

```
│  ┌──────────────────────────────┐      │
│  │ 20살 경영학과, 차분한 후배…   │      │
│  └──────────────────────────────┘      │
│  [✨ AI로 정리하기] → 폼으로 이동·검수    │
```

---

## 8. 비목표 (이번 전략 범위 밖)

- NPC 간 **장소 기반** 자동 등장/퇴장 (제거된 설계 — `dialogue_npc_cap` + 이름·화자 선택 유지)
- 비주얼 **빌더** (UGC_MVP Phase 2)
- 자유 텍스트 **무인 자동 저장** (검수 단계 생략)
- `player`를 월드 에디터에 다시 넣기
- 이벤트 에디터와 NPC 스키마 통합 (별도 스프린트)

---

## 9. 리스크·완화

| 리스크 | 완화 |
|--------|------|
| AI 파싱 환각 (잘못된 major) | 검수 UI 필수, confidence 낮으면 필드 비움 |
| 폼↔JSON 필드 불일치 | §4 단일 정본, 공유 타입 |
| 프롬프트 토큰 증가 | `background`는 200자 cap, `dialogue_npc_cap` 유지 |
| `personality`와 `appearance_for_ai` 혼동 | UI 섹션 분리 + 도움말 (현재 import 시 personality→appearance 혼합 제거) |

---

## 10. 성공 지표

- 신규 UGC 월드의 **JSON 모드 사용 비율** < 10% (폼·AI로 충분)
- NPC `major`/`personality` 저장률 > 80% (폼 필드 추가 후)
- 플레이 로그/수동 QA: “다른 과로 소개” **재현율 감소**
- Phase B: AI 정리 → 저장 전 **편집률** 측정 (100% 자동 수용이면 품질 의심)

---

## 11. 다음 액션 (구현 착수 순서)

1. **이 문서 리뷰** — §4 필드·§6 Phase 경계 확정
2. **Phase A** — `worldEditorSimple.ts` + `WorldEditorPage` + `prompt_optimizer` background
3. **Phase A** — `backend/src/schemas/npc.py` 최소 검증
4. **Phase B** — structure-draft API + 에디터 버튼
5. **`DEVELOPMENT.md`** · [`WORLD_VISUAL_AI_ROADMAP.md`](WORLD_VISUAL_AI_ROADMAP.md) 교차 링크 유지

---

## 12. 용어 정리

| 용어 | 의미 |
|------|------|
| **3계층** | UI 입력 / DB JSON / LLM·이미지 실행 |
| **3-Way** | 폼 / AI 정리 / JSON 고급 |
| **Canonical NPC** | §4 — UGC가 따를 저장 필드 정본 |
| **간편 모드** | `WorldEditorPage` `editorMode === 'simple'` |
| **컴팩트 NPC** | `_format_compact_npcs` 출력 — 턴당 subset |

이 문서가 **NPC 저작·스키마·프롬프트 연동**의 단일 진실 출처다. 구현 PR은 Phase별로 쪼개고, 완료 시 §5 매트릭스의 “목표” 열을 ✅로 갱신한다.
