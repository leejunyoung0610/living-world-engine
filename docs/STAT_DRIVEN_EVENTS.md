# 스탯 기반 이벤트 시스템 (작업 문서)

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-05-10 |
| 상태 | **PR-1 백엔드 완료 / 베타 후 데이터 도입 보류** (코드는 들어갔지만 캠퍼스 `events.json` 이 옛 스키마라 실제 발동 0회) |
| 관련 문서 | `UGC_MVP_PLAN.md` · `ARCHITECTURE.md` · `BETA_DEV_EXECUTION.md` · `STREAMING.md` |
| 관련 코드 | `backend/src/engine/events.py`, `backend/src/engine/state.py`, `backend/src/engine/game_loop.py`, `backend/src/api/routes/play.py` |

> **핵심 원칙 (사용자 명시)**
> - **감정·관계** (affection / trust / romance / fear / respect) 는 LLM 의 이야기 흐름에서 자연스럽게 `update_relationship` 으로 변동 — *기존 그대로*.
> - **자원 스탯** (hp / stress / focus 등) 과 **플래그** 만 이벤트의 `resource_stat` / `flag_set` / `narrative` 효과로 가끔 움직인다.
> - 따라서 `apply_effects` 는 의도적으로 `relationship` 효과를 미지원 — 누가 실수로 써도 조용히 무시 (테스트 `test_relationship_effect_is_ignored_in_pr1` 로 박제).

이 문서는 **이번 주 보고서 + 다음 스프린트 실행 계획**의 단일 진실 출처(single source of truth)다.
대규모 PR로 가지 않고 **단계별로 쪼개어 PR**한다.

---

## 0. 이번 주까지의 작업 요약 (보고서용 한 컷)

### 시스템(월드) ↔ 캐릭터 분리 (UGC)

월드는 **세계관 + NPC**만 저장하고, 플레이어 캐릭터는 **플레이를 시작할 때마다** 사용자가 정한다.

| 영역 | 변경 |
|------|------|
| **월드 저장 (`backend/src/api/routes/worlds.py`)** | `WorldCharactersBody`(`npcs` 기본 `[]`, `extra="allow"`). `_normalize_characters_for_storage`로 저장 시 `player` 제거. |
| **플레이 API (`backend/src/api/routes/play.py`)** | `POST /api/play/start` — 새 세션은 `player` 필수(422 처리), 이어하기는 `player` 없이 동작. `_merge_template_and_entry_player`로 템플릿 NPC + 입장 player 합성. |
| **브리프 API** | `GET /api/play/world/{id}/brief` — 입장 화면용 (목록명·스토리 제목·`description`·`world_setting`·NPC 목록·옛 `suggested_player` 보조). |
| **엔진 (`engine/state.py`)** | `load_from_dicts`는 `npcs`만 필수. `player` 없으면 임시 플레이어로 채움(템플릿 로딩 호환). |
| **프론트** | `/play/setup/:worldId` 신설 — 브리프 조회 → 이어하기 자동 시도 → 캐릭터 폼(`name·class·stats`) → 입장. `?forceNew=1`이면 새 캐릭터로 시작. 탐색·마이페이지의 "플레이"는 모두 이 페이지로 라우팅. |
| **월드 에디터** | 플레이어/스텟 입력 제거, NPC 중심. JSON 모드 도움말도 `npcs` 필수로 정리. |

### 세계관 설정 (`world_setting`)

목록·카드용 짧은 `description`과 분리된 **상세 세계관 문자열**을 도입했다. LLM 시스템 프롬프트(static 블록)에 「세계 한 줄 요약」 + 「세계관 설정」으로 들어가 프롬프트 캐시 적용 대상이 된다. 레거시 `setting`은 비었을 때만 보조로 사용.

### 번들 월드 보강

`backend/src/worlds/campus/world.json`을 관악 캠퍼스 톤·구역·사실·변수까지 채워, 새 세계관 흐름의 **참조 예시**로 사용.

### 인프라·운영

- Worktree 잔재(예전 `characters.player is required` 검증)를 메인과 동일하게 동기화.
- `docker compose up -d --build --force-recreate api web`로 최신 이미지로 재기동, `/health`·웹 200 확인.

### 테스트

- `test_api_worlds`, `test_api_play`, `test_user_journey`(스모크), `test_prompt_optimizer` 정합성 유지 — 22+개 통과.
- 추가 케이스: 새 세션은 `player` 필수 422, 브리프 응답에 `world_setting` 노출.

---

## 1. 다음 섹션 — 스탯 기반 이벤트

### 1-1. 왜 필요한가

지금 `EventManager`는 **3가지 조건 타입**(`turn_range`, `variable_threshold`, `relationship_threshold`)과 **일부 효과**(`world_variable`, `player_stat`)를 지원한다. 하지만 UGC가 모르는 사람도 만들 수 있으려면 — **플레이어 스탯**을 직접 조건으로 거는 게 너무 흔한 요구다 (예: "스트레스 ≥ 7이면 번아웃 이벤트").

지금은 그게 **돌아가는 듯하지만 정의되어 있지 않다**:
- `EventManager._evaluate_condition`에 `player_stat_threshold`가 없음.
- 효과 적용 경로가 분산(`game_loop` 내부, LLM 툴 응답 등)되어 UGC 작성자에게 가시화되지 않음.
- 이벤트가 발동된 후 **무엇이 변했는지** 응답·히스토리에 반영되지 않음 (사용자에게 보이지 않음).

### 1-2. 결과 목표 (DoD)

1. UGC 작성자가 **에디터에서 조건 템플릿**으로 "스트레스 ≥ N", "호감도 ≥ M" 형태의 이벤트를 5분 내 만들 수 있다.
2. 턴이 진행될 때 조건이 평가되고, **효과가 게임 상태에 반영**되며, **턴 응답 메타**에 발동 사실이 포함된다.
3. 같은 시드·같은 입력이면 같은 결과 (랜덤 트리거에도 시드 고정 가능).
4. **테스트**: 조건 평가, 쿨다운, 효과 적용, 우선순위 케이스가 단위 테스트로 보호된다.

### 1-3. 비목표 (Out of Scope, 이번 스프린트)

- 분기형 시나리오 그래프(이벤트 → 다른 이벤트 트리거)
- LLM 호출로 이벤트 본문 생성 (별도 스프린트)
- NPC 간 자율 행동(behavior tree)

---

## 2. 데이터 스키마 초안

### 2-1. 이벤트(`events.json` 또는 DB `events_data`)

```json
{
  "events": [
    {
      "id": "burnout_warning",
      "name": "번아웃 조짐",
      "description": "잠을 거의 못 잤다. 손이 떨린다.",
      "narrative_hint": "거울 속 얼굴이 낯설다.",
      "condition": {
        "type": "player_stat_threshold",
        "stat": "stress",
        "op": ">=",
        "value": 7
      },
      "effects": [
        { "type": "player_stat", "key": "stress", "change": -2 },
        { "type": "player_stat", "key": "focus", "change": -1 }
      ],
      "cooldown": 6,
      "priority": 5,
      "tags": ["health", "warning"]
    }
  ]
}
```

### 2-2. 신규/확장 조건 타입

| 타입 | 의미 | 필드 |
|------|------|------|
| `player_stat_threshold` (**신규**) | 플레이어 스탯 임계값 | `stat`, `op`, `value` |
| `compound` (**신규**) | AND/OR 조합 | `op`(`"and"`/`"or"`), `conditions[]` |
| `time_window` (**신규**) | 일·시간대 조건 | `min_day`, `max_day`, `phase`("day"/"night") |
| `flag` (**신규**) | 게임 플래그 set/cleared | `key`, `value` |
| `turn_range` | (기존) 턴 구간 | — |
| `variable_threshold` | (기존) 월드 변수 | — |
| `relationship_threshold` | (기존) NPC 관계치 | — |

### 2-3. 효과 타입 (정리)

| 타입 | 의미 |
|------|------|
| `player_stat` | 플레이어 스탯 가감 (clamp 옵션) |
| `world_variable` | 월드 변수 가감 |
| `relationship` | 특정 NPC 관계치 가감 |
| `flag_set` | 플래그 설정 |
| `narrative` | LLM에 힌트만 추가 (state 변경 없음) |

clamp는 월드의 `standard_stats[stat].min/max`(있으면)를 따른다.

---

## 3. 실행기 설계

### 3-1. 트리거 시점

`GameEngine.process_turn` 흐름에 다음 순서로 끼운다:

1. 사용자 메시지 해석 → LLM 응답
2. LLM 툴 결과(`update_game_state`)로 **상태 1차 적용**
3. **`EventManager.tick_cooldowns()` → `check_events()` → `apply_effects()`** ← 신설 단계
4. 응답·히스토리에 이벤트 메타 포함

### 3-2. 우선순위·중복 방지

- `priority` 큰 순으로 평가 → **이번 턴 발동 가능 후보**.
- 같은 턴에 최대 N개(기본 1, 월드별 설정) 발동.
- 쿨다운에 들어간 이벤트는 다음 턴부터 평가 제외.

### 3-3. 시드·재현성

- `world.seed` 또는 세션 시작 시 생성한 seed를 `WorldState`에 저장.
- 랜덤 트리거(`probability`)는 `(seed, turn, event_id)` 해시로 결정 → 같은 입력 = 같은 결과.

### 3-4. 응답 페이로드 확장

`PlayTurnResponse.events_triggered` 항목에 효과 요약 추가.

```json
{
  "events_triggered": [
    {
      "event_id": "burnout_warning",
      "description": "잠을 거의 못 잤다. 손이 떨린다.",
      "applied_effects": [
        { "type": "player_stat", "key": "stress", "before": 7, "after": 5 }
      ]
    }
  ]
}
```

---

## 4. UGC 에디터(프론트)

- **간편 모드**에 "조건 템플릿" 드롭다운: `스트레스 임계값`, `호감도 임계값`, `특정 일차에 도달` 등.
- 선택하면 폼 입력값을 받아서 위의 JSON으로 직렬화.
- 상세는 **JSON(고급) 모드**에서 그대로 편집 가능.
- 입장 화면(브리프)에는 표시하지 않는다 — 이벤트는 플레이 중 자연스럽게 노출.

---

## 5. 작업 분해 (PR 단위)

| # | 작업 | 산출물 |
|---|------|--------|
| **PR-1** | `EventManager`에 `player_stat_threshold`, `compound` 추가 + 단위 테스트 | `events.py`, `test_events.py` |
| **PR-2** | 효과 적용기 분리(`engine/effects.py` 또는 `events.py`내 `apply_effects`) + clamp/flag 처리 | `events.py`, `state.py`, `test_effects.py` |
| **PR-3** | `process_turn` 통합 + 응답 페이로드 확장 + 시드 도입 | `game_loop.py`, `routes/play.py`, 응답 모델 |
| **PR-4** | 시드·재현성 결정론 테스트 + 회귀 테스트 묶음 | `test_event_replay.py` |
| **PR-5** | UGC 에디터 — 조건 템플릿 (간편 모드) | `WorldEditorPage.tsx`, `worldEditorSimple.ts` |
| **PR-6** | 캠퍼스/아케인 번들에 신규 조건 사용 예시 1~2개 추가 | `worlds/*/events.json` |
| **PR-7** | 문서 정리: 본 문서 → 결과 절 채우고 `UGC_MVP_PLAN.md`/`ARCHITECTURE.md`에 링크 | 본 문서, 두 docs |

각 PR은 **단위 테스트 + 변경된 곳의 통합 테스트 1개 이상**을 요구한다.

---

## 6. 리스크 / 결정 필요한 항목

| 항목 | 메모 |
|------|------|
| 이벤트가 같은 턴에 너무 많이 터지는 경우 | 기본 캡 `max_events_per_turn=1`. 월드별로 `world_variables.max_events_per_turn` 가능. |
| LLM 툴 결과와 이벤트 효과가 같은 키를 동시에 변경 | 이벤트 효과는 **툴 결과 적용 후** 적용. 같은 턴 충돌 시 이벤트가 마지막 값. |
| UGC 작성자가 잘못된 스키마를 저장 | `WorldCreate`/`Update` 시 events 스키마도 가벼운 파서로 검증 (오류 시 422). |
| 시드를 어디에 둘 것인가 | `WorldState.seed`(int). 세션 첫 생성 시 결정. 응답·로그에 노출 여부는 보안 영향 없음. |

---

## 7. 일정 (가안 — 솔로·병행 기준)

| 주차 | 목표 |
|------|------|
| **Week 1** | PR-1, PR-2 (조건·효과 자체) |
| **Week 2** | PR-3, PR-4 (런타임 통합 + 시드/테스트) |
| **Week 3** | PR-5, PR-6 (UGC + 예시 데이터), PR-7 (문서) |

각 주 끝에 **이 문서 § 0의 보고서 단락 갱신**.

---

## 8. 변경 로그

- 2026-05-10 — 초안 작성 (계획 + 분리 작업 정리). 이번 주 보고서 기준점.
- 2026-05-10 — **PR-1 백엔드 구현 완료**. 사용자 결정으로 데이터(이벤트 정의) 도입은 베타 피드백 후 결정.

---

## 9. PR-1 완료 보고 (2026-05-10)

### 9-1. 무엇이 코드에 들어갔나

| 영역 | 변경 |
|------|------|
| `engine/state.py` | `update_player_stat(key, change, clamp=None)`, `set_flag(key, value)`, `get_flag(key, default)` 추가. 자원 스탯 / 플래그 전용 — 관계 스탯은 기존 `update_relationship` 만 사용. |
| `engine/events.py` | 모듈 docstring에 "감정 vs 자원" 분리 원칙 명시. 조건 4종(`resource_stat_threshold`, `flag`, `time_window`, `compound`) + 효과 3종(`resource_stat`, `flag_set`, `narrative`) + `_resolve_resource_clamp` (`world.stats_schema.resource[key].{min,max}` 기준 clamp). 같은 턴 발동 캡 기본값 `DEFAULT_MAX_EVENTS_PER_TURN=1`. |
| `engine/game_loop.py` | `process_turn` 내부 이벤트 루프에서 `apply_effects` 호출, `applied_effects` 를 `events_triggered` 메타에 포함. 월드별 `world_variables.max_events_per_turn` 으로 캡 덮어쓰기 가능. |
| `tests/unit/test_events.py` (+253 줄) | 새 조건/효과 + 우선순위 + relationship 효과 무시 회귀 테스트. |
| `tests/unit/test_game_engine_events.py` (+17 줄) | 기본 캡 1 검증, 캡 풀었을 때 다중 발동 검증. |

총 **+33 단위 테스트**, 전체 214 passed.

### 9-2. 왜 "베타 후"로 보류했는가

[`PRODUCTION_ROADMAP.md` § 갭 분석](PRODUCTION_ROADMAP.md) 의 카테고리 비교에서 **체감 임팩트가 큰 기능(스트리밍 / 재생성 / 페르소나 저장)** 이 우선이라는 결론에 따라:
- 이 코드는 **백엔드 메커니즘만 들어가있는 상태** — 캠퍼스/아케인의 `events.json` 이 옛 `trigger:"random"+probability` 스키마라 새 `condition` 평가기에선 모두 False → 실제 발동 0.
- 데이터(이벤트 정의)와 LLM 시스템 프롬프트의 `narrative_hint` 주입은 **베타 피드백 후 진행** 결정.

### 9-3. 베타 후 재개 시 남은 작업

| # | 작업 | 비고 |
|---|------|------|
| PR-A | 캠퍼스 `events.json` 신규 스키마로 마이그레이션 (`time_window` + `flag` + `resource_stat` 효과 1~2개) | 실제 발동 시작 |
| PR-B | `narrative_hint` 를 다음 턴 `system_prompt` 의 dynamic 블록에 1턴만 주입 | "이야기 속에서 반영" 의 핵심 |
| PR-C | 채팅의 `[이벤트] ...` 별도 메시지를 토스트/배지로 격리 | 이야기와 시스템 분리 |
| PR-D | 헤더에 자원 스탯 게이지·배지 (`hp 80/100`, `stress 0→5↑`) | 변화 가시화 |
| PR-5 (원래 계획) | UGC 에디터 — 조건 템플릿 (간편 모드) | UGC 진입 장벽 ↓ |
