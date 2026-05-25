# 2026-05-25 — 비주얼 AI, 탐색·홈 카드, 에디터·테스트 변경 요약

운영 확인 시: 백엔드 재시작(`uvicorn`), Alembic `upgrade head`(신규 마이그레이션), 프론트는 `npm run build` 또는 `npm run dev`로 반영.

## 백엔드

| 영역 | 내용 |
|------|------|
| 이미지 생성 | Replicate 기반 커버·NPC 초상 생성 플로우, 일 예산·월별 쿼터 서비스 |
| 저장·미러 | 선택적 Cloudflare R2 미러 (`r2_storage`); 최종 저장은 HTTPS URL |
| Worlds API | `POST …/generate-cover`, `POST …/npcs/{id}/generate-portrait`; 공개·탐색 응답에 `_cover_image_url` 정책(HTTPS 등) 준수 |
| 탐색 목록 | `GET /api/worlds/explore` 각 항목에 `cover_image_url` 포함 → 홈 카드에서 썸네일 가능 |
| 설정 | `.env.example` 및 `backend/src/utils/config.py` 에 이미지·R2·쿼터·비용 관련 키 |

## 마이그레이션

- `0013_image_cover_quotas.py`
- `0014_image_gen_cost_daily.py`
- `0015_npc_avatar_quotas.py`

## 프론트엔드

| 영역 | 내용 |
|------|------|
| 홈 탐색 | `ExploreWorldSummary.cover_image_url` 기반 카드 상단 썸네일(HTTPS만) |
| 월드 에디터 | AI 커버·NPC 초상 UX, 간편 필드 연동 등 |
| Vite 프록시 | 로컬 Kakao 등 콜백 호스트 꼬임 방지(`/api`, `/health` 프록시 `changeOrigin`) |
| 라우팅 | `App.tsx` — 에디터·신규/편집 라우트·키 처리 |

## 품질·릴린트

- `backend/tests/conftest.py`: 유닛 기본값으로 `REQUIRE_INVITE_CODE_FOR_SIGNUP=false` (로컬 `.env`가 true여도 테스트 통과).
- 월드·이미지 관련 단위 테스트 보강; Replicate 미설정 503 테스트는 테스트 시 `REPLICATE_API_TOKEN=""` 로 격리.
- Ruff: `long_term_memory` 미사용 import 제거, `play_persistence` 중복 import 제거.

## 관련 상세 로드맵

- 월드·NPC 비주얼 기능 범위: `docs/WORLD_VISUAL_AI_ROADMAP.md`
- 배포: `docs/DEPLOYMENT.md`
