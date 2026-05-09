# 베타 출시 — 실행 개발 문서 (개발자·에이전트용)

이 문서는 **`docs/UGC_MVP_PLAN.md`의 Ready but Gated**를 코드로 옮기기 위한 **구현 단위(Epic) · 완료 조건(DoD) · 코드 위치**를 정의한다.  
기획·정책 숫자의 **정본**은 `UGC_MVP_PLAN.md`를 따르고, 구현 후 **이 문서의 체크박스와 아래 「기준선」을 갱신**한다.

---

## 사용 방법 (에이전트·페어 프로그래밍)

1. **한 번에 Epic 하나**를 끝까지 가져간다 (예: Epic A만).
2. 각 Task 끝에 **DoD**를 만족하는지 확인하고 체크박스를 갱신한다.
3. **설정 추가 시** `backend/src/utils/config.py` + `.env.example` + (필요 시) README 한 줄.
4. **DB 스키마 변경 시** Alembic 리비전 추가, `poetry run python -m alembic upgrade head`로 검증.
5. **테스트:** 새 보안·정책 로직은 `backend/tests/unit/` 또는 `backend/tests/integration/`에 최소 1케이스.

---

## 기준선 — 이미 있는 것 (구현 전 확인)

| 영역 | 상태 | 참고 |
|------|------|------|
| 인증·JWT | 있음 | `backend/src/api/routes/auth.py`, `deps.py` |
| 초대 코드 | **검증 있음(플래그)** | `REQUIRE_INVITE_CODE_FOR_SIGNUP` + `invite_codes` (Epic C) |
| 월드 CRUD·공개 탐색 | 있음 | `backend/src/api/routes/worlds.py` |
| 탐색 페이지네이션 | 있음 | `GET /api/worlds/explore` → `{ items, total, limit, offset }`, `limit` 기본 20·최대 100 |
| 플레이·세션·엔진 | 있음 | `backend/src/api/routes/play.py`, `GameEngine`, `play_sessions` |
| 프론트 플레이 URL | **`/play/:sessionId`** | 공유는 **세션 UUID** 기준 (월드 slug 직링크 아님) |
| 전역 422·미처리 예외 | 있음 | `backend/src/api/error_handlers.py`, `main.py` |
| SQLAlchemy 오류 500 | 있음 | `main.py` |
| CORS | **설정값 의존** | `settings.cors_origins` — 프로덕션에서 도메인 고정은 **운영 설정 과제** |
| `/health` | **DB ping** | `SELECT 1` 실패 시 503 |
| 턴당 usage 집계(엔진) | 있음 | `UsageTracker` (`game_loop`) — **플랫폼 일일 쿼터·알림과는 별개** |
| Docker / CI | **부분** | Compose·`docker-build` workflow (Epic A·B). Sentry·JSON 로그는 Epic H |
| 플랫폼 일일 턴 쿼터 | **부분** | `user_daily_turn_usage` + `POST .../turn` (Epic D). Redis 미사용 · 플랫폼 단일 API 키 |

---

## Epic A — 컨테이너 & 로컬 실행 (배포 전제)

**목표:** 한 명이 `docker compose up`으로 API+DB(+선택 프론트)를 띄울 수 있다.

| Task | DoD |
|------|-----|
| [x] Backend `Dockerfile` (Poetry, multi-stage 권장) | `docker/Dockerfile.api`, 엔트리포인트에서 Alembic 후 `uvicorn` |
| [x] Frontend `Dockerfile` 또는 정적 빌드 + nginx | `frontend/Dockerfile` + `nginx.conf` (`/api` 프록시) |
| [x] `docker-compose.yml` | `db` + `api` + `web`, `DATABASE_URL`, 헬스체크·볼륨 |
| [x] `.dockerignore` | 루트·`frontend/` 각각 |
| [x] README에 **로컬 compose 절차** | 「Docker Compose」소절 참고 |

**파일 힌트:** 저장소 루트, 기존 `pyproject.toml`, `frontend/package.json`.

---

## Epic B — 프로덕션 배포·HTTPS·시크릿

**목표:** 실제 URL로 HTTPS 접속, 비밀은 저장소에 없음.

| Task | DoD |
|------|-----|
| [x] 호스팅 결정 (예: EC2+RDS, 또는 단일 VM+관리형 DB) | [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) §1 — 베타 권장안·확장 시 EC2+RDS |
| [x] `DATABASE_URL` / `JWT_SECRET` 배포 환경 전용 | `.gitignore`에 `.env`; `.env.example`·`DEPLOYMENT.md` §3 |
| [ ] TLS (Let’s Encrypt / 관리형 인증서) | **실제 배포 URL에서 자물쇠** 확인 시 완료 — 절차는 `DEPLOYMENT.md` §2 |
| [x] (선택) GitHub Actions | [`.github/workflows/docker-build.yml`](../.github/workflows/docker-build.yml) — 이미지 빌드 검증(`main`/PR/`workflow_dispatch`) |
| [x] (권장) AWS SSM / Secrets Manager | `DEPLOYMENT.md` §3 + [`UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) §6·§7 |

**파일 힌트:** `.github/workflows/`, 인프라는 별도 IaC 여부 팀 결정.

---

## Epic C — 가입 게이트

**목표:** 초대 없이 무제한 가입 불가, (선택) 전체 유저 상한.

| Task | DoD |
|------|-----|
| [x] 초대 코드 **검증** | `require_invite_code_for_signup` 시 DB 검증, 403/422 + 한국어 메시지 |
| [x] 초대 코드 저장소 | `invite_codes` (Alembic `0005`), `create_invite_code.py` |
| [x] `MAX_TOTAL_USERS` | 설정 시 가입 전 `COUNT(users)` 비교, 초과 시 403 |
| [x] Feature flag | `REQUIRE_INVITE_CODE_FOR_SIGNUP` (기본 false — 로컬·Docker 편의) |

**파일 힌트:** `backend/src/api/routes/auth.py`, `backend/src/db/models/`, `migrations/`, `config.py`.

---

## Epic D — 턴 쿼터 (비용 방어)

**목표:** 플랫폼 키 사용 시 **유저·일 단위** 턴 상한 (문서의 예: 20턴/일).

| Task | DoD |
|------|-----|
| [x] 정책 정의 | 플랫폼 단일 `ANTHROPIC_API_KEY` — 일일 턴 쿼터는 **전 유저** 대상(Epic D) |
| [x] `POST .../turn` 전·후 | 선검사 + 성공 시 기록, 초과 시 **429** + 한국어 메시지 (`play_start` 는 LLM 없음 → 미집계) |
| [x] 일일 리셋 | **UTC 달력일** (`turn_quota.utc_usage_date`, `UGC_MVP_PLAN` §8 정렬) |
| [x] 저장소 | PostgreSQL `user_daily_turn_usage` — 멀티 워커 공유. (Redis는 미도입) |

**파일:** `backend/src/services/turn_quota.py`, `play.py`, `config.py`, Alembic `0006`.

---

## Epic E — 비용 상한 알림 & 긴급 셧다운

**목표:** 문서의 일일 비용 임계·`EMERGENCY_SHUTDOWN` 경로.

| Task | DoD |
|------|-----|
| [x] 일일 플랫폼 비용 추정 집계 | 플랫폼 턴 성공 후 `UsageTracker.total_cost` 증분 → `platform_cost_daily` (UTC 일자, Alembic `0008`) |
| [x] 임계 초과 시 웹훅 | `PLATFORM_COST_ALERT_WEBHOOK_URL` + `PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD` — JSON `{"text":...}` 1일 1회 |
| [x] `EMERGENCY_SHUTDOWN` | `True`면 **신규 가입 503**, **플레이 턴(LLM) 전부 503** |

**파일:** `config.py`, `services/platform_cost.py`, `play.py`, `auth.py`(signup), `db/models/platform_cost_daily.py`.

---

## Epic F — 보안 최소선

| Task | DoD |
|------|-----|
| [x] CORS 프로덕션 | `DEBUG=false` 일 때 `CORS_ORIGINS` 에 `*` 이면 기동 거부 (`api/security.py`) |
| [x] 레이트 리밋 | `slowapi` — 가입 12/분, 로그인 30/분, 턴 90/분 (`RATE_LIMITING_ENABLED`, 테스트는 env 로 off) |
| [x] `/health` 확장 | `Depends(get_db)` + `SELECT 1`, 실패 시 503 |
| [x] 보안 헤더 | `SecurityHeadersMiddleware` — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` |

**파일:** `main.py`, `api/limiter.py`, `api/security.py`, `api/routes/auth.py`, `play.py`.

---

## Epic G — BYOK (중단 · 플랫폼 단일 키)

**현재 정책:** per-user 키(BYOK) 없음. 서버 **`ANTHROPIC_API_KEY` 하나**로 모든 턴 호출. Alembic **`0009`** 가 `users` 에서 BYOK 관련 컬럼 제거.

| Task | DoD |
|------|-----|
| [—] (이전) BYOK | 코드·UI·`/me/llm-key` 제거됨. 문서·기획 재검토 시 Epic G 재정의 가능 |

---

## Epic H — 관측

| Task | DoD |
|------|-----|
| [x] Sentry (또는 동등) FastAPI 연동 | `SENTRY_DSN` 시 `sentry_sdk` + Starlette/FastAPI 통합; 전역·SQLAlchemy 500 핸들러에서 `capture_exception` |
| [x] 구조화 로그 (JSON) | `STRUCTURED_LOGGING=true` 시 JSON 한 줄; 액세스 로그에 `request_id`, `path`, `status_code`, `duration_ms`; `X-Request-Id` 응답 헤더 |

**파일:** `main.py`, `api/error_handlers.py`, `api/request_context_middleware.py`, `utils/logging_setup.py`, `config.py`, `tests/unit/test_observability.py`.

---

## Epic I — E2E / 스모크

| Task | DoD |
|------|-----|
| [x] 스크립트 또는 pytest + TestClient 체인 | `backend/tests/smoke/test_user_journey.py` — 가입 → 월드 생성 → play start → turn (`@pytest.mark.smoke`, Stub 엔진) |
| [x] CI에서 마커 분리 | [`.github/workflows/pytest.yml`](../.github/workflows/pytest.yml) — `pytest -m "not integration and not e2e"`; `pyproject.toml`에 `smoke`·`e2e` 마커 등록 |

---

## Epic J — 법무 최소

| Task | DoD |
|------|-----|
| [ ] 이용약관·개인정보 처리방침 정적 페이지 또는 링크 | 회원가입 플로우에서 접근 가능 |
| [ ] BYOK 시「운영자 기술적 복호화 가능」문구 | `UGC_MVP_PLAN.md` §6 반영 |

---

## Epic K — 공유·플로우 명확화 (제품)

**목표:** “친구에게 보내는 링크”가 기대와 일치.

| Task | DoD |
|------|-----|
| [ ] 문서·UI에 **세션 링크** 명시 | `/play/{session_id}` — 소유자만 이어하기 등 정책 문구 |
| [ ] (선택) 월드 진입용 짧은 링크 | `?world=` 또는 별도 라우트 — 구현 시 권한·스팸 검토 |

---

## 권장 순서 (의존성)

1. **A → B** (어디에도 올릴 수 있는 형태)
2. **C → D** (가입·플레이 제한)
3. **F** (노출 직후)
4. **E**, **G** (비용·키 — 문서상 MVP 필수면 G를 앞당김)
5. **H, I, J** 병행 가능
6. **K**는 UX·문서 위주

---

## 참고 링크

- [`docs/PRODUCTION_ROADMAP.md`](PRODUCTION_ROADMAP.md) — **실서비스 전환** 시 갭 분석·단계별 개발 계획(신뢰·법무·결제·월드 3트랙 등)
- [`docs/UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) — 정책·비용·보안 원칙
- [`DEVELOPMENT.md`](../DEVELOPMENT.md) — 엔진·UGC 코드 브리핑
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — 배포 후 UGC 흐름 다이어그램 반영 권장
