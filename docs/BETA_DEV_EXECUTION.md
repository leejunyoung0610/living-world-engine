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
| 초대 코드 필드 | **수용만** | `signup`의 `invite_code` — **DB·정책 검증 없음** (주석 그대로) |
| 월드 CRUD·공개 탐색 | 있음 | `backend/src/api/routes/worlds.py` |
| 탐색 페이지네이션 | 있음 | `GET /api/worlds/explore` → `{ items, total, limit, offset }`, `limit` 기본 20·최대 100 |
| 플레이·세션·엔진 | 있음 | `backend/src/api/routes/play.py`, `GameEngine`, `play_sessions` |
| 프론트 플레이 URL | **`/play/:sessionId`** | 공유는 **세션 UUID** 기준 (월드 slug 직링크 아님) |
| 전역 422·미처리 예외 | 있음 | `backend/src/api/error_handlers.py`, `main.py` |
| SQLAlchemy 오류 500 | 있음 | `main.py` |
| CORS | **설정값 의존** | `settings.cors_origins` — 프로덕션에서 도메인 고정은 **운영 설정 과제** |
| `/health` | **정적 OK만** | DB ping 없음 |
| 턴당 usage 집계(엔진) | 있음 | `UsageTracker` (`game_loop`) — **플랫폼 일일 쿼터·알림과는 별개** |
| Docker / CI / AWS / Sentry | 없음 | 이 문서 Epic에서 다룸 |

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
| [ ] 정책 정의 | FREE(플랫폼 키) vs BYOK 경로 구분 — BYOK는 문서대로 플랫폼 집계 제외 |
| [ ] `POST .../turn` (및 필요 시 `start`) 전 검사 | 초과 시 402/429 + 한국어 메시지 |
| [ ] 일일 리셋 기준 시각 고정 | `UGC_MVP_PLAN.md` §8 (UTC 권장) |
| [ ] 저장소 | DB 컬럼/테이블 또는 Redis — 멀티 워커 시 **공유 저장소** 필수 |

**파일 힌트:** `backend/src/api/routes/play.py`, `config.py`, 신규 `services/quota.py` 등.

---

## Epic E — 비용 상한 알림 & 긴급 셧다운

**목표:** 문서의 일일 비용 임계·`EMERGENCY_SHUTDOWN` 경로.

| Task | DoD |
|------|-----|
| [ ] 일일 플랫폼 비용 추정 집계 | `UsageTracker` 또는 별도 집계와 연결 방법 명시 |
| [ ] 임계 초과 시 Slack(또는 웹훅) 알림 | 환경변수로 웹훅 URL |
| [ ] `EMERGENCY_SHUTDOWN` (이름은 설정으로) | True면 플랫폼 키 턴 거절 또는 가입/플레이 전부 503 |

**파일 힌트:** `config.py`, 백그라운드 잡은 Cron/워커 vs 요청 시 체크 중 선택.

---

## Epic F — 보안 최소선

| Task | DoD |
|------|-----|
| [ ] CORS 프로덕션 도메인 화이트리스트 | 와일드카드 `*` 금지 (자격 증명 사용 시 특히) |
| [ ] 레이트 리밋 | `slowapi` 등 — 로그인·가입·턴 엔드포인트 우선 |
| [ ] `/health` 확장 | DB `SELECT 1` (또는 ORM ping) — 로드밸런서용 |
| [ ] (선택) 보안 헤더 | nginx 또는 Starlette 미들웨어 |

**파일 힌트:** `main.py`, `nginx` 설정.

---

## Epic G — BYOK

**목표:** 사용자 API 키 암호화 저장, FREE vs BYOK 분기.

| Task | DoD |
|------|-----|
| [ ] 키 암호화 (Fernet 등) | 마스터 키는 환경 시크릿, 평문 DB 컬럼 없음 |
| [ ] LLM 호출 경로에서 BYOK 우선 | 키 없으면 플랫폼 키 + 쿼터 |
| [ ] TierManager (또는 동등) | 설정·모델 라우팅이 한 곳에서 결정 |
| [ ] 설정 페이지 UI | 프론트에서 키 입력·마스킹·삭제 |

**파일 힌트:** `backend/src/engine/llm.py`, `config.py`, `frontend/src/pages/`.

---

## Epic H — 관측

| Task | DoD |
|------|-----|
| [ ] Sentry (또는 동등) FastAPI 연동 | 500·미처리 예외 수집 |
| [ ] 구조화 로그 (JSON) | 요청 id, 경로, 상태코드 — 검색 가능 |

---

## Epic I — E2E / 스모크

| Task | DoD |
|------|-----|
| [ ] 스크립트 또는 pytest + TestClient 체인 | 가입(또는 fixture 유저) → 월드 생성 → play start → turn 1회 |
| [ ] CI에서 마커 분리 | API 키 필요 테스트는 `pytest -m "not live"` 등 |

**파일 힌트:** `docs/TESTING.md`, `backend/tests/`.

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

- [`docs/UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) — 정책·비용·보안 원칙
- [`DEVELOPMENT.md`](../DEVELOPMENT.md) — 엔진·UGC 코드 브리핑
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — 배포 후 UGC 흐름 다이어그램 반영 권장
