# 프로덕션 배포 가이드 (Epic B)

베타 실행 계획은 [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md) Epic B와 [`UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) §6·§7(비밀·Docker·배포 원칙)과 맞춘다.  
**배포 당일 체크리스트:** [`BETA_DEPLOYMENT_CHECKLIST.md`](BETA_DEPLOYMENT_CHECKLIST.md)

## 1. 호스팅 선택 (요약)

**권장(소규모 베타):** 관리형 PostgreSQL(RDS, Supabase, Neon 등) + **컨테이너 1대**(Fly.io, Railway, 단일 EC2/VM)에 API·Nginx(프론트)를 함께 두거나, 프론트는 객체 저장소+CDN으로 분리한다.  
**이유:** 인프라 부담이 적고, HTTPS·시크릿은 플랫폼이나 리버스 프록시 한 겹으로 정리하기 쉽다.

**확장 시:** 트래픽·규정·팀 운영이 커지면 EC2(ASG)+RDS+ALB(또는 ECS/Fargate)로 쪼개는 것이 일반적이다. 이 저장소는 Dockerfile·compose로 **어디에나 올릴 수 있는 이미지**를 전제로 한다.

## 2. TLS (HTTPS)

- **관리형:** ALB, Cloudflare, Fly/Railway 기본 TLS 등 — 인증서를 직접 갱신하지 않아도 된다.
- **자체 VM:** Caddy(자동 Let’s Encrypt) 또는 Certbot + Nginx.  
**DoD:** 사용자가 실제 배포 URL을 열었을 때 주소창 **자물쇠(유효한 인증서)** 가 보이면 Epic B TLS 항목을 완료로 본다.

## 3. 시크릿 (`DATABASE_URL`, `JWT_SECRET`, API 키)

- **저장소에 넣지 않는다.** `.env`는 [`.gitignore`](../.gitignore)에 포함되어 있다. 샘플만 [`.env.example`](../.env.example).
- **프로덕션:** 호스팅 플랫폼의 환경 변수 또는 **AWS SSM Parameter Store / Secrets Manager**에 두고, 런타임에 주입한다. EC2에 `echo`로만 `.env`를 만드는 방식은 베타 이후 반드시 교체하는 것을 권장([`UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) §6).

필수 변수(이름은 앱 설정과 동일):

| 변수 | 용도 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 |
| `JWT_SECRET` | JWT 서명(추측 불가, ≥32바이트 권장) |
| `ANTHROPIC_API_KEY` | Claude 호출 |
| `CORS_ORIGINS` | 허용 브라우저 오리진(콤마 구분) |

베타 프로덕션 템플릿: [`.env.production.example`](../.env.production.example)  
점검 스크립트: `poetry run python backend/scripts/check_beta_env.py --strict` ([`BETA_DEPLOYMENT_CHECKLIST.md`](BETA_DEPLOYMENT_CHECKLIST.md) §2)

Docker로 띄울 때는 `docker-compose.yml`의 로컬 DB URL을 **배포 환경 변수로 덮어쓴다.**

## 4. 이미지·마이그레이션

- API: `docker/Dockerfile.api` — 엔트리에서 `alembic upgrade head` 후 `uvicorn`.
- 웹: `frontend/Dockerfile` — 빌드 산출물 + Nginx(`nginx.conf`에서 `/api` 프록시). 배포 시 API 호스트명을 **실제 백엔드 URL**에 맞게 수정해야 할 수 있다(compose는 서비스명 `api` 사용).

## 5. 플랫폼 턴 쿼터 (Epic D)

- `.env`: `ENFORCE_PLATFORM_TURN_QUOTA=true`, `PLATFORM_DAILY_TURN_LIMIT=20` 등. **UTC 자정**마다 일자가 바뀌며 카운트 리셋.
- 적용 대상은 **모든 로그인 유저**(플랫폼 단일 `ANTHROPIC_API_KEY`). `user_daily_turn_usage`·마이그레이션 `0006` 이후.

## 6. 가입 게이트 (초대 코드)

- **의미:** `REQUIRE_INVITE_CODE_FOR_SIGNUP=true`일 때 **신규 `signup`만** 유효한 `invite_codes` 행이 있어야 한다. 이미 가입한 계정의 **로그인**에는 초대 코드가 필요 없다.
- DB 마이그레이션 `0005` 후 예시:  
  `poetry run python backend/scripts/create_invite_code.py BETA-ABC --max-uses 10`
- `MAX_TOTAL_USERS`로 전체 계정 수 상한을 둘 수 있다(미설정이면 무제한).

## 7. 비용 알림·긴급 셧다운 (Epic E)

- **`PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD`**, **`PLATFORM_COST_ALERT_WEBHOOK_URL`** — Slack Incoming Webhook 등 `{"text":"..."}` 수신 URL.
- 추정 비용은 엔진 **`UsageTracker`** 와 동일 단가(토큰·캐시)로 턴당 증분 합산(플랫폼 키 경로만).
- **`EMERGENCY_SHUTDOWN=true`** — 신규 가입 차단 + **플레이 턴( LLM ) 전부** 503.

## 8. LLM API 키 (플랫폼 단일)

- **`ANTHROPIC_API_KEY` 하나**로 모든 유저 턴을 호출한다(서버 env).
- 예전 per-user 키 컬럼은 마이그레이션 **`0009`** 에서 제거한다. 배포 후 `alembic upgrade head` 필수.

## 9. 레이트 리밋 (Epic F)

- `RATE_LIMITING_ENABLED=true`(기본)일 때 slowapi 적용. 부하에 따라 한도는 코드(`auth`·`play` 라우트)에서 조정.
- 프로덕션에서 `DEBUG=false`이면 `CORS_ORIGINS`에 와일드카드 `*` 를 쓸 수 없다.

## 10. 관측 — Sentry·구조화 로그 (Epic H)

- **`SENTRY_DSN`**: 비우면 Sentry 비활성. 설정 시 FastAPI/Starlette 통합으로 미처리 예외·DB 500 핸들러 예외가 이슈로 전송된다. `SENTRY_ENVIRONMENT`(미설정 시 `DEBUG`에 따라 development/production), `SENTRY_TRACES_SAMPLE_RATE`(기본 0)는 선택.
- **`STRUCTURED_LOGGING=true`**: 루트 로그와 액세스 로그(`living_world.access`)를 JSON 한 줄로 내보낸다. 필드 예: `request_id`, `path`, `http_method`, `status_code`, `duration_ms`. 응답 헤더 **`X-Request-Id`** 로 클라이언트·Sentry 태그와 대응 가능.

## 11. 소셜 로그인 — 카카오 OAuth (선택)

- **켜는 조건:** `KAKAO_LOGIN_ENABLED=true` 일 때만 `/api/auth/kakao/*` 라우트가 활성된다(꺼져 있으면 404).
- **필요 환경변수:**
  - `KAKAO_CLIENT_ID` — 카카오 디벨로퍼스 「내 애플리케이션 → 앱 키 → REST API 키」.
  - `KAKAO_CLIENT_SECRET` — 「보안」에서 발급. 「사용 안 함」 상태면 비워둔다(콘솔과 일치 필수).
  - `KAKAO_REDIRECT_URI` — **비워두면** 요청 호스트(예: `localhost:8080`, `172.30.x.y:8080`, `https://your-app.example`) 기준으로 **자동 도출**된다. 카카오 콘솔에 사용할 모든 호스트의 Redirect URI 를 등록해 두면 한 빌드로 모두 사용 가능. 특정 값으로 고정하려면 콘솔 등록값과 **글자 단위로 동일**하게 적는다.
  - `KAKAO_POST_LOGIN_REDIRECT` — 콜백 후 토큰을 들고 돌아올 프론트 URL. 비우면 호스트 기준 `/oauth/callback` 사용.
- **로컬 Vite (`npm run dev`, 포트 `:5173`):** `frontend/vite.config.ts` 의 `/api` 프록시는 **`changeOrigin: false`** 를 쓴다. `true` 이면 `Host`가 `127.0.0.1:8000`으로 바뀌어 카카오 콜백 후 폴백 URL이 **`http://127.0.0.1:8000/oauth/callback`** 이 되고, 그 경로는 FastAPI가 아니라 SPA(Vite)에만 있어 **404로 ‘로그인 실패’**처럼 보인다. 콘솔에는 `http://localhost:5173/api/auth/kakao/callback` 과 실제 접속 호스트와 **글자 단위로 같은** 값을 등록한다(`localhost` vs `127.0.0.1`은 서로 다른 URI).
- **리버스 프록시(Nginx 등) 사용 시 주의:** 백엔드가 외부에서 본 호스트(포트 포함)를 알 수 있도록 `proxy_set_header Host $http_host;`, `X-Forwarded-Host`, `X-Forwarded-Port`, `X-Forwarded-Proto` 를 함께 넘겨야 한다. uvicorn 은 `--proxy-headers --forwarded-allow-ips=*` 로 신뢰. 본 저장소의 `frontend/nginx.conf`·`docker/Dockerfile.api` 가 기본 적용되어 있다.
- **카카오 콘솔 체크리스트:**
  - 「제품 설정 → 카카오 로그인」 활성, 「Redirect URI」 등록.
  - 「동의항목」 — `profile_nickname`(필수), `account_email`(선택, 동의 안 받아도 합성 식별자로 가입은 가능).
  - 운영 도메인이 `https://` 인지 확인. 카카오는 운영 환경에서 일반적으로 https 만 허용한다.
- **DB:** 마이그레이션 **`0010`** 이 `users.auth_provider`, `users.kakao_sub`, `users.password_hash` (nullable) 를 추가한다. 배포 후 `alembic upgrade head` 필수.
- **로그인 흐름:** 프론트 「카카오로 로그인」 → `GET /api/auth/kakao/authorize` → 카카오 동의 → `GET /api/auth/kakao/callback?code=...` → 백엔드가 JWT 발급 후 `KAKAO_POST_LOGIN_REDIRECT#access_token=...` 로 302. 프론트 `/oauth/callback` 페이지가 토큰을 `localStorage` 에 저장하고 `/` 로 진입.
- **회귀 케이스:**
  - 동일 `email` 의 로컬 계정이 이미 있으면 자동으로 `kakao_sub` 만 연결한다(비밀번호 보존, `auth_provider="local"` 유지).
  - 카카오 전용 계정은 `password_hash=NULL` → 비밀번호 로그인 차단(401).

## 12. 공식(시스템) 월드 시드

- `backend/src/worlds/<slug>/{world,characters,events}.json` 파일을 DB 의 `visibility="public"` 월드로 등록한다. 「운영팀」 라벨의 시스템 유저 1명(`system@platform.local`, `password_hash=NULL`, `auth_provider="system"`)을 만들어 그 소유로 등록 — 로그인 불가능, 기존 UGC 정책(계정당 월드 상한 등) 영향 없음.
- 실행 (Docker)::

      docker compose exec -T -e PYTHONPATH=/app api \
        poetry run python backend/scripts/seed_official_worlds.py

  `--slug campus` 로 단일 월드만, `--force` 로 기존 row 삭제 후 재생성 가능. 기본 동작은 같은 이름의 월드를 찾아 `world_data`·`characters_data`·`events_data` 만 갱신해 진행 중인 세션 ID 보존.
- 결과 확인::

      docker compose exec -T db psql -U postgres -d living_world \
        -c "SELECT name, visibility, owner_id FROM worlds WHERE visibility='public';"

## 13. CI

GitHub Actions에서 Docker 이미지 빌드만 검증한다(푸시 시 자동 배포는 별도 workflow·시크릿이 필요하다).
