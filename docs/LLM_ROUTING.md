# LLM Turn Router (RouteLLM v1) — 설계 문서

| 항목 | 내용 |
|------|------|
| 상태 | **설계만** (구현 예정 — Phase 4) |
| 작성일 | 2026-07-23 |
| 관련 | `OPTIMIZATION_PLAN.md` Day 15 · `README.md` Phase 4 · `game_loop.py` · `llm.py` |
| 목표 | 대화 품질 유지 + 턴당 API 비용 추가 절감 (Sonnet 단일 $0.019 → 목표 ~$0.015) |

---

## 1. 배경

- Phase 1~3(프롬프트 캐시, Single-Pass, ContextManager)로 **~47%** 절감 ($0.036 → $0.019/턴, 164턴 실측).
- Phase 4 **경량 모델 라우팅**은 Day 15 계획에 있었으나, 「유저 입력만으로 Haiku/Sonnet 분기」 기준을 정하지 못해 미구현.
- 2026년 LLM 라우팅 연구·상용 도구(RouteLLM, LiteLLM 등)는 **쿼리 분류** 중심이지만, 본 프로젝트는 **게임 상태(snapshot)** 를 함께 쓰면 규칙 기반 v1이 가능.

**핵심 원칙**

> LLM이 상태를 **제안**하고, 시스템이 **검증**한다 — 라우터도 동일.  
> **애매하면 Sonnet**, Haiku는 안전 턴만, 실패 시 **Sonnet 캐스케이드 1회**.

---

## 2. 아키텍처 (v1 — 턴 단위)

```
game_loop.process_turn()
  → TurnRouter.select(ctx)     # Sonnet | Haiku
  → llm.process_turn(..., model=decision.model)
  → validator / WorldState     # 모델 무관
  → (Haiku & escalate?) → Sonnet 재시도 1회
  → usage_tracker (모델별 단가 이미 지원)
```

**신규 파일 (구현 시)**

| 파일 | 역할 |
|------|------|
| `backend/src/engine/turn_router.py` | Tier A/B/C 규칙, `RouteDecision` |
| `backend/tests/unit/test_turn_router.py` | 규칙 케이스 15+ |
| `config.py` | `LLM_ROUTING_ENABLED`, `LLM_ROUTING_MIN_B_SCORE` |

**기존 수정**

- `llm.py` — `process_turn(..., model: str | None = None)` per-call override
- `game_loop.py` — 라우터 호출, `routing_meta` API 응답(선택)

---

## 3. 판단 입력 (`TurnRouteContext`)

| 신호 | 출처 | 용도 |
|------|------|------|
| `turn`, `day` | `WorldState.snapshot()` | 초반 턴 보호 |
| `user_input` | 플레이어 | 길이·키워드 |
| `pending_event_hints` | `game_loop` | 이벤트 직후 |
| `last_turn_had_event` | 세션/직전 결과 | EventCard 후 |
| `regenerate` | `play.py` | 재생성 |
| `relationships` | snapshot | 임계값 근접 |
| `flags` | snapshot | Canon 후보 |
| `npc_in_scene` | prompt 빌드 추정 | 0 = solo 내레이션 |
| `memories_hit` | memory search | LTM 3+ = 중요 |
| `recent_relationship_delta` | 직전 N턴 | 변화 없음 → Haiku 후보 |

---

## 4. 규칙 — Tier A (무조건 Sonnet)

하나라도 해당 시 Haiku **금지**.

| ID | 조건 |
|----|------|
| A1 | `regenerate == true` |
| A2 | `turn <= 2` |
| A3 | `pending_event_hints` 비어있지 않음 |
| A4 | 직전 턴 `events_triggered` 존재 |
| A5 | 스토리 키워드 (고백, 이별, 사귀, 헤어, 빚, 상환, 퇴사, 약속, 화해, 배신, 결혼, 동거 …) |
| A6 | NPC 이름 2명 이상 언급 |
| A7 | 관계 수치가 월드 마일스톤 임계 −5 이내 |
| A8 | Canon/flag 확정 후보 키워드 |
| A9 | `len(user_input) > 80` |
| A10 | `memories_hit >= 3` |

---

## 5. 규칙 — Tier B (Haiku 후보)

Tier A **전부 해당 없을 때만** 점수화. **B ≥ 3** 이면 Haiku (기본 `MIN_B_SCORE=3`).

| ID | 조건 | 예 |
|----|------|-----|
| B1 | 입력 ≤ 20자 | "응", "알겠어" |
| B2 | 이동·일상 패턴 | "집에 간다", "자러 간다" |
| B3 | `npc_in_scene == 0` | 혼자 내레이션 |
| B4 | 최근 3턴 관계 Δ = 0 | 가벼운 구간 |
| B5 | `memories_hit <= 1` | 맥락 적음 |
| B6 | `turn >= 5` | 워밍업 이후 |

**Tier C:** A 없음 + B < 3 → **Sonnet** (기본값).

---

## 6. 캐스케이드 (품질 안전망)

Haiku 실행 후 아래 중 하나면 **Sonnet 1회 재시도**:

| ID | 실패 신호 |
|----|-----------|
| E1 | `response` 길이 < 40자 |
| E2 | scene에 NPC 있는데 `tool_used == false` |
| E3 | validator가 relationship/flag 전부 drop |
| E4 | 감정 키워드인데 `relationship_changes` 빈 배열 |
| E5 | `dialogue_split` 화자 블록 0개 |

로그: `🧭 route=haiku escalate=sonnet reason=...`

---

## 7. v2 (향후) — 태스크 분리 라우팅

턴 단위 대신 **역할** 고정:

| 서브태스크 | 모델 |
|------------|------|
| `update_game_state` (Tool JSON) | Haiku |
| NPC 대사 (텍스트, tools 없음) | Sonnet |

Single-Pass와 방향이 다름(2-call). Tool Use 품질 vs 서사 품질 분리. 구현·스트리밍 경로 수정 필요.

---

## 8. v3 (향후) — 데이터 기반 튜닝

- v1 로그: `turn`, `model`, `tier`, `reasons[]`, `cost`, `escalated`
- Haiku `escalate` 비율 > 15% → `MIN_B_SCORE` 상향
- 월드별 `world_variables.llm_route_profile`: `conservative` | `economy`

ML/BERT 분류기는 **오프라인 로그 축적 후** 검토 (RouteLLM 등).

---

## 9. 기대 효과 (보수적 가정)

| 설정 | Haiku 비율 | 턴당 비용 (참고) |
|------|-----------|------------------|
| Sonnet only (현재) | 0% | ~$0.019 |
| v1 보수적 (B≥3) | 25~40% | ~$0.015~0.017 |
| v1 공격적 (B≥2) | 50~60% | ~$0.012~0.014 (품질 리스크↑) |

측정: `UsageTracker` + Anthropic `usage`, 164턴 세션과 동일 산식.

---

## 10. 발표·보고서용 한 줄

> Phase 4 **Turn Router**: 게임 상태(이벤트·관계·Canon·NPC) 기반 Tier A/B/C 규칙으로 Sonnet/Haiku 분기, 실패 시 캐스케이드 — ML 없이 v1, Tool/서사 분리는 v2.

---

## 11. 구현 체크리스트 (발표 후)

- [ ] `turn_router.py` + `test_turn_router.py`
- [ ] `llm.py` model override
- [ ] `game_loop.py` 연동 + escalate
- [ ] `LLM_ROUTING_ENABLED` env
- [ ] 20턴 A/B 실측 (민근이 월드)
- [ ] `FINAL_REPORT.md` Phase 4 절 갱신
