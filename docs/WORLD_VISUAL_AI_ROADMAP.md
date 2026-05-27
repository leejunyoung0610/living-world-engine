# 월드·NPC 비주얼 AI 로드맵

> 상태 스냅샷: 커버·NPC 초상까지 **자동 생성 루트 반영**. `characters.npcs[].portrait_image_url` 저장 · 공개 API `portrait_url` · 일 예산 공유 풀(`IMAGE_NPC_AVATAR_COST_ESTIMATE_USD`) · R2 미러 프리픽스 `avatars/…`.

---

## 이번 주 계획 (요약)

| 구간 | 내용 |
|------|------|
| Day 1–2 | R2 통합 ✅ |
| Day 3 | UTC 일 예산 ✅ |
| Day 4–6 | NPC 초상 생성 API·프론트·쿼터·테스트 **반영** |
| Day 7 | 통합 테스트·베타 안내 |

커버 일 예산 코드: `backend/src/services/image_gen_daily_budget.py`.

### R2 환경 변수

`R2_ACCOUNT_ID`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL` 이 **모두** 채워져야 미러가 동작합니다. 하나라도 비면 Replicate 가 준 URL만 DB에 저장됩니다. 구현: `backend/src/services/r2_storage.py`.

**중요:** Replicate 가 주는 URL은 **임시(만료)** 일 수 있습니다. 오래 쓰려면 R2(또는 자체 스토리지)를 켜서 **영구 공개 URL**로 미러하는 것이 안전합니다.

**PUT `/api/worlds/{id}`** 는 클라이언트가 `world`/`characters` JSON 전체를 보내므로, 과거에는 `cover_image_url` 키가 빠지면 DB에서도 사라지는 경우가 있었습니다. 이제 **키가 빠진 경우**에는 기존 커버·히어로·썸네일 URL과 NPC `portrait_image_url`을 유지하고, **`cover_image_url`: `""`처럼 명시한 경우에만** 삭제합니다.

---

## ✅ 이미 있음

- `cover_image_url` 필드 (`world_setting` 등과 함께 `world` JSON)
- 공개 상세 히어로 이미지 (`/world/browse` 상세 페이지)
- 에디터에서 URL 직접 입력 (간편 모드 「커버 이미지 URL」)
- 공개 목록 세부의 NPC 카드 초상 미리보기 (`portrait_url`)
- 간편 월드 편집기 NPC 행별 「AI 초상」
- **홈 탐색 카드 커버** — `GET /api/worlds/explore` 의 `cover_image_url` → `HomePage` 썸네일 (HTTPS)


## ⏳ 다음 단계 (권장 순서)

### Phase 1: 월드 커버 자동 생성 (필수)

| 항목 | 방향 |
|------|------|
| UX | Character.AI / 제타류 — **세계관(또는 한 줄 소개)·장르 기반으로 커버 자동 생성**을 기본/권장 옵션으로 |
| 재생성 | **월드당 같은 기간 내 재생성 N회**(예: 4회) — 정책 확정 필요 |
| 쿼터 | **계정당 월 M장**(예: 20장) — DB 카운터 + UTC 월 단위 리셋 권장 |
| 기술 | Claude는 이미지 미생성 → **이미지 API**(OpenAI Images, Replicate, 자체 호스팅 등) + 생성 프롬프트는 텍스트 LLM 또는 템플릿 |
| 산출물 | 생성 결과는 **HTTPS URL**로 저장 → 기존 `cover_image_url`과 동일 경로로 반영 가능 |
| 예상 공수 | 3–4일 (프로바이더 선정·키·실패 처리·UI·테스트 포함) |

**구현 훅(본 저장소):**

- `backend/src/utils/config.py` — 이미지 제공자 API 키·모델 옵션(플래그로 비활성 시 기존 수동 URL만)
- 새 테이블 예: `user_monthly_visual_quota(user_id, year_month, cover_generations, npc_avatar_generations)` 또는 기존 `user_daily_turn_usage` 패턴 참고
- `POST /api/worlds/{id}/covers/generate` (예시) — 소유자만, 월드 `visibility` 무관 가능, 성공 시 `world_data.cover_image_url` 갱신
- `frontend` — 월드 에디터에 「AI로 커버 생성」「재생성 (n/4)」버튼, 쿼터 표시

---

### Phase 2: NPC 아바타 자동 생성 — **본 저장소 현재 상태**

| API | ``POST /api/worlds/{world_id}/npcs/{npc_id}/generate-portrait`` (JWT 소유자) |
| 저장 | ``characters_data.npcs[].portrait_image_url`` (HTTPS) |
| 초상 프롬프트 텍스트 | ``npcs[].appearance_for_ai`` 우선(간편 폼「캐릭터 특징」), 없으면 ``personality`` → ``background`` → ``appearance`` → ``description`` 중 첫 문자열. 초상 생성에는 ``location`` 미사용(LLM용 장소 필터는 별도로 JSON에 둘 수 있음). |
| 노출 | ``PublicNpcBrief.portrait_url`` — `/api/worlds/public/{id}` |
| 모델 | ``IMAGE_MODEL_NPC_AVATAR`` (기본 `flux-schnell`, 이름에 ``sdxl`` 포함 시 폭·높이 모드) |
| 쿼터 | 테이블 ``user_monthly_avatar_quotas`` / ``world_monthly_avatar_quotas`` |
| 일 비용 | ``IMAGE_NPC_AVATAR_COST_ESTIMATE_USD`` — ``image_gen_daily_budget_usd`` 과 **합산** 차단 |

---

## 의사결정 체크리스트 (착수 전)

1. **이미지 제공자**: 단일 vendor vs 추상화(인터페이스 + 구현체 1개)
2. **저장 방식**: 외부 URL만 vs 업로드 후 자체 호스팅(S3 등)
3. **쿼터**: 「월드당 재생성 4회」가 **달 단위인지·월드 수명 단위인지** 명확히
4. **비용**: 서버 단일 키(턴 쿼터와 동일 철학) vs 추후 사용자별 한도

---

문서 업데이트 시기: 기능 착수·완료에 맞춰 본 파일과 `docs/2026-05-25_visual_ai_explore_frontend.md`(날짜별 요약) 교차 반영을 권장합니다.

**NPC 저작 (폼·스키마·LLM 필드):** [`docs/NPC_CHARACTER_AUTHORING_STRATEGY.md`](NPC_CHARACTER_AUTHORING_STRATEGY.md) — `appearance_for_ai`는 비주얼 계층, `major`·`personality`·`background`는 대화 계층(Phase A~B).
