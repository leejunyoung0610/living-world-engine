# 월드·NPC 비주얼 AI 로드맵

> 상태 스냅샷: `cover_image_url`, URL 직접 입력, 공개 상세 히어로 표시까지 **반영 완료** (`world_data.cover_image_url`, HTTPS만).

---

## ✅ 이미 있음

- `cover_image_url` 필드 (`world_setting` 등과 함께 `world` JSON)
- 에디터에서 URL 직접 입력 (간편 모드 「커버 이미지 URL」)
- 공개 상세 페이지 히어로 이미지 표시 (`/world/:id`)

---

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

### Phase 2: NPC 아바타 자동 생성 (중요)

| 항목 | 방향 |
|------|------|
| 목표 | NPC마다 초상 이미지 — **비주얼 노벨 / 캐릭터 카드** 느낌 |
| 데이터 | `characters.npcs[].portrait_image_url`(HTTPS) 같은 필드를 단계적으로 도입하거나, `npc id → url` 매핑 JSON |
| 노출 | 공개 상세 `npcs`에 `avatar_url`(또는 동일 패턴) 추가, 카드 레이아웃 |
| 쿼터 | Phase 1 쿼터와 **공유 풀** 또는 **별도 상한** — 정책 결정 |
| 예상 공수 | 2–3일 |

**구현 훅:**

- `_public_npc_briefs` / `PublicNpcBrief` — 선택 필드 `portrait_url` 추가
- `WorldBrowsePage` — NPC 카드 좌측 또는 상단에 썸네일
- 일괄 생성 vs NPC별 버튼 — UX 결정 후 API 설계

---

## 의사결정 체크리스트 (착수 전)

1. **이미지 제공자**: 단일 vendor vs 추상화(인터페이스 + 구현체 1개)
2. **저장 방식**: 외부 URL만 vs 업로드 후 자체 호스팅(S3 등)
3. **쿼터**: 「월드당 재생성 4회」가 **달 단위인지·월드 수명 단위인지** 명확히
4. **비용**: 서버 단일 키(턴 쿼터와 동일 철학) vs 추후 사용자별 한도

---

문서 업데이트 시기: 기능 착수·완료에 맞춰 본 파일과 `DEVELOPMENT.md` 교차 반영을 권장합니다.
