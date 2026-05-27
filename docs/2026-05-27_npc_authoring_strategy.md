# 2026-05-27 — NPC 저작 3계층 · 3-Way 입력 전략 스냅샷

> **정본:** [`NPC_CHARACTER_AUTHORING_STRATEGY.md`](NPC_CHARACTER_AUTHORING_STRATEGY.md)  
> 이 파일은 날짜별 요약·착수 메모용이다.

## 배경

- UGC 작성자 대부분은 JSON을 다루기 어렵다.
- 현재 간편 폼은 **이름·역할·초상(appearance_for_ai)** 위주 → `major`·`personality`·`background`는 JSON에만 넣거나 import 시 유실·혼동.
- `major: "무용과"`를 JSON에 넣어도 **다른 과로 자기소개**하는 사례 → LLM용 필드가 폼/프롬프트에 제대로 안 실리거나, `background`/`role`과 모순.

## 결론 (한 줄)

**텍스트→DB 자동화는 어렵지 않다.** UI(폼·AI 정리)와 저장(JSON 스키마)을 분리하고, 실행층(`prompt_optimizer`)이 정본 필드만 읽게 맞추면 된다.

## 3계층

| # | 레이어 | 역할 |
|---|--------|------|
| 1 | UI | 폼 · 자유 텍스트(+AI) · JSON 고급 — JSON 기본 노출 X |
| 2 | DB | `World.characters_data.npcs[]` — Pydantic 검증 (도입 예정) |
| 3 | 실행 | 대화 LLM / 초상 AI / 공개 brief — 필드별 소비 매트릭스 |

## 3-Way 입력

| 방식 | 비중 | 상태 |
|------|------|------|
| A 폼 | ~95% | 부분 (Phase A) |
| B 자유 + AI 정리 | ~5% | 미구현 (Phase B) |
| C JSON | 고급 | ✅ 유지 |

## Phase 우선순위

1. **Phase A** — ✅ 2026-05-27 반영 (폼·프롬프트·npc 스키마)
2. **Phase B** — `npc-structure-draft` API + 「AI로 정리하기」+ **검수 후 저장**
3. **Phase C** — JSON 모드·스키마 도움말·422

## 오늘 코드와의 갭 (핵심만)

| 항목 | 파일 |
|------|------|
| 간편 폼 필드 부족 | `frontend/src/utils/worldEditorSimple.ts` |
| NPC 스키마 검증 없음 | `backend/src/api/routes/worlds.py` |
| `background` LLM 미사용 | `backend/src/engine/prompt_optimizer.py` |
| `speech_style` / `speaking_style` 불일치 | 템플릿 vs optimizer |

## 착수 전 확인

- [ ] §4 Canonical 필드 확정 (age 넣을지 등)
- [ ] Phase B API 쿼터·BYOK 정책
- [ ] `location` 폼에서 완전 제거 vs 레거시만 보존 (전략: **보존만**)

## 관련

- 비주얼 AI: [`WORLD_VISUAL_AI_ROADMAP.md`](WORLD_VISUAL_AI_ROADMAP.md)
- UGC player 분리: [`STAT_DRIVEN_EVENTS.md`](STAT_DRIVEN_EVENTS.md) §0
- 대화 NPC subset: [`DEVELOPMENT.md`](../DEVELOPMENT.md) — `dialogue_npc_cap`
