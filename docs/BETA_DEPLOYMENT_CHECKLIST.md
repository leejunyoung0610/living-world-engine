# 베타 배포 체크리스트

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-05-27 |
| 목적 | Living World Engine 베타 배포를 위한 체계적 점검 |
| 대상 | Cursor + 운영자 |
| 상태 | 배포 전 검증 단계 |
| 관련 | [`DEPLOYMENT.md`](DEPLOYMENT.md) · [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md) · [`.env.example`](../.env.example) |

---

## 코드베이스 대조 메모 (2026-05-27 스냅샷)

아래는 **이 저장소 기준**으로 체크리스트 원문과 다른 점·로컬 점검 결과다. 배포 전 다시 실행해 갱신할 것.

| 항목 | 실제 |
|------|------|
| 단위 테스트 | `poetry run pytest backend/tests/unit` → **259 passed** (「200+」보다 구체적) |
| 프론트 빌드 | `cd frontend && npm run build` → **성공** (`tsc -b && vite build`) |
| 프론트 lint | `package.json`에 **`npm run lint` 없음** — 빌드(`tsc`)로 타입 검증 |
| Git | `main` **push 완료** (2026-05-27, 5 commits) |
| Ruff | **`poetry run ruff check backend/` 통과** |
| Docker (로컬) | `docker compose build` + `/health` + alembic **0015 (head)** |
| Env 점검 | `poetry run python backend/scripts/check_beta_env.py [--strict]` |
| LLM 모델 env | **`LLM_MODEL`** (별칭 `sonnet` / `sonnet45` 가능). `ANTHROPIC_MODEL` 아님 |
| BYOK | **제거됨** (마이그레이션 `0009`). **`BYOK_MASTER_KEY` 불필요** |
| 비용 알림 env | **`PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD`** (예: `2.0`). `PLATFORM_DAILY_COST_THRESHOLD` 아님 |
| NPC 초상 월 한도 | 기본 **`IMAGE_GEN_NPC_PER_USER_MONTHLY=60`** (`.env.example` / `config.py`) |
| Alembic head | **`0015_npc_avatar_quotas`** |

---

## 사용 방법

1. 각 섹션을 순서대로 진행
2. 체크박스 `[ ]` → `[x]`로 표시
3. 막힌 부분은 **메모** 남기기
4. **모든 P0** 완료 후 배포

**우선순위**

- 🔴 **P0**: 배포 전 필수
- 🟡 **P1**: 베타 시작 시점에 필수
- 🟢 **P2**: 베타 운영 중 처리

---

## 🔴 P0: 배포 전 필수 (Pre-Deployment)

### 1. 코드 베이스 정리

- [x] `main` 브랜치 최신 상태 확인 (2026-05-27)
- [x] 미커밋 변경사항 정리/커밋 (5 commits pushed)
- [x] 단위 테스트 통과 (**259 passed**)
- [x] 프론트엔드 빌드 (`npm run build`)
- [x] 백엔드 lint (`ruff check backend/`)

**로컬 점검 명령**

```bash
git pull origin main && git status
poetry run pytest backend/tests/unit -q
cd frontend && npm run build
poetry run ruff check backend/
```

### 2. 환경 변수 점검

> **정본 이름:** [`.env.example`](../.env.example) · [`.env.production.example`](../.env.production.example) · [`backend/src/utils/config.py`](../backend/src/utils/config.py)

**자동 점검 (값 미출력)**

```bash
poetry run python backend/scripts/check_beta_env.py          # 로컬·스테이징
poetry run python backend/scripts/check_beta_env.py --strict # 베타 프로덕션 권장
```

**로컬 `.env` 스냅샷 (2026-05-27)** — `--strict` 기준 **미충족 항목** (프로덕션 배포 전 호스팅에 설정):

| 항목 | 로컬 | 프로덕션 필요 |
|------|------|----------------|
| `JWT_SECRET` | dev 기본값 | `openssl rand -hex 32` 로 교체 |
| `DEBUG` | `true` | `false` |
| `CORS_ORIGINS` | localhost/LAN | `https://실제도메인` only |
| R2 다섯 값 | 미설정 | 전부 또는 Replicate 임시 URL 감수 |
| Sentry·비용·쿼터·`MAX_TOTAL_USERS` | 미설정 | `.env.production.example` 참고 |
| `ANTHROPIC`·`REPLICATE`·`DATABASE_URL` | ✅ 로컬용 설정됨 | 호스팅 DB URL로 교체 |

#### 필수

**데이터베이스·인증**

- [ ] `DATABASE_URL` — 프로덕션 PostgreSQL
- [ ] `JWT_SECRET` — ≥32바이트 난수 (`openssl rand -hex 32`)

**LLM (플랫폼 단일 키 — per-user BYOK 없음)**

- [ ] `ANTHROPIC_API_KEY`
- [ ] `LLM_MODEL=claude-sonnet-4-5-20250929` 또는 `sonnet` / `sonnet45`
- [ ] `ENABLE_SINGLE_PASS=true` (기본 true)
- [ ] (선택) `LLM_MAX_TOKENS=768`

**이미지 생성 (Replicate)**

- [ ] `REPLICATE_API_TOKEN`
- [ ] `IMAGE_MODEL_COVER=black-forest-labs/flux-1.1-pro`
- [ ] `IMAGE_MODEL_NPC_AVATAR=black-forest-labs/flux-schnell`
- [ ] `IMAGE_COVER_ASPECT_RATIO=16:9`

**Cloudflare R2 (영구 URL — 다섯 값 모두 필요)** — 미설정 시 Replicate URL 만료로 커버·초상 404. 자세한 원인·복구: [`docs/IMAGE_STORAGE.md`](IMAGE_STORAGE.md)

- [ ] `R2_ACCOUNT_ID`
- [ ] `R2_ACCESS_KEY`
- [ ] `R2_SECRET_KEY`
- [ ] `R2_BUCKET=lwe-images` (또는 본인 버킷)
- [ ] `R2_PUBLIC_URL=https://images.your-domain.com` (슬래시 없이)

**카카오 OAuth (선택)**

- [ ] `KAKAO_LOGIN_ENABLED=true`
- [ ] `KAKAO_CLIENT_ID`
- [ ] `KAKAO_CLIENT_SECRET` (콘솔에서 사용 안 함이면 비움)
- [ ] 카카오 콘솔 Redirect URI 등록 — `https://your-domain.com/api/auth/kakao/callback` 등 **실제 호스트와 글자 단위 일치** ([`DEPLOYMENT.md`](DEPLOYMENT.md) §11)

**보안**

- [ ] `DEBUG=false`
- [ ] `CORS_ORIGINS=https://your-domain.com,...` (와일드카드 `*` 금지)
- [ ] `RATE_LIMITING_ENABLED=true`

**관측**

- [ ] `SENTRY_DSN`
- [ ] `SENTRY_ENVIRONMENT=production`
- [ ] `SENTRY_TRACES_SAMPLE_RATE=0.1` (또는 0)
- [ ] `STRUCTURED_LOGGING=true`

**비용 방어 (베타 보수적 예시)**

- [ ] `ENFORCE_PLATFORM_TURN_QUOTA=true`
- [ ] `PLATFORM_DAILY_TURN_LIMIT=20`
- [ ] `PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD=2.0`
- [ ] `PLATFORM_COST_ALERT_WEBHOOK_URL` (Slack Incoming Webhook)
- [ ] `IMAGE_GEN_DAILY_BUDGET_USD=2.0`
- [ ] `IMAGE_GEN_PER_USER_MONTHLY=20`
- [ ] `IMAGE_GEN_NPC_PER_USER_MONTHLY=60` (기본값; 50으로 줄이려면 명시 설정)
- [ ] `EMERGENCY_SHUTDOWN=false`

**가입 정책 (베타)**

- [ ] `REQUIRE_INVITE_CODE_FOR_SIGNUP=true`
- [ ] `MAX_TOTAL_USERS=200`

### 3. 데이터베이스 마이그레이션

- [x] 로컬 Docker: `alembic current` → **0015 (head)** (2026-05-27)
- [ ] 프로덕션 DB 백업 (기존 데이터 있을 때)
- [ ] 프로덕션 `alembic upgrade head`
- [ ] 테이블 존재 확인
  ```bash
  psql "$DATABASE_URL" -c "\dt"
  ```

**마이그레이션 목록 (저장소 기준)**

| Rev | 파일 | 요약 |
|-----|------|------|
| 0001 | `0001_create_users.py` | users |
| 0002 | `0002_create_worlds.py` | worlds |
| 0003 | `0003_world_visibility.py` | visibility |
| 0004 | `0004_play_sessions.py` | play_sessions |
| 0005 | `0005_invite_codes.py` | invite_codes |
| 0006 | `0006_platform_turn_quota.py` | 일 턴 쿼터 |
| 0007 | `0007_byok_encrypted_key.py` | (레거시 BYOK — 0009에서 제거) |
| 0008 | `0008_platform_cost_daily.py` | platform_cost_daily |
| 0009 | `0009_remove_byok_columns.py` | BYOK 컬럼 제거 |
| 0010 | `0010_kakao_oauth.py` | 카카오 OAuth 컬럼 |
| 0011 | `0011_world_genres_popularity.py` | genres·popularity |
| 0012 | `0012_world_likes.py` | world_user_likes |
| 0013 | `0013_image_cover_quotas.py` | image_cover_quotas |
| 0014 | `0014_image_gen_cost_daily.py` | image_gen_cost_daily |
| 0015 | `0015_npc_avatar_quotas.py` | image_avatar_quotas |

### 4. 외부 서비스 계정

- [ ] **Anthropic** — 결제·Spending limit·API 키·알림
- [ ] **Replicate** — 결제·한도·토큰·Flux 1회 테스트
- [ ] **Cloudflare R2** — 버킷·공개 접근·커스텀 도메인·Access Key
- [ ] **Sentry** — FastAPI 프로젝트·DSN·Slack 알림
- [ ] **Slack** — `#living-world-alerts`·Webhook 테스트
- [ ] **카카오 개발자** — 앱·도메인·Redirect URI·동의항목

### 5. 호스팅 환경

- [ ] 플랫폼 선택 (Fly.io / Railway / Render / VPS)
- [ ] 관리형 PostgreSQL
- [ ] 위 환경 변수 전부 등록
- [ ] 도메인 + SSL (자물쇠)

### 6. Docker 이미지 검증

- [x] 로컬 `docker compose build` (2026-05-27)
- [x] 헬스체크 `curl http://localhost:8000/health` → `{"status":"ok","database":"ok"}`
- [ ] 프로덕션 호스팅에 동일 이미지 배포

---

## 🟡 P1: 베타 시작 시 필수 (Beta Launch)

### 7. HTTPS / TLS

- [ ] 배포 URL 접속·자물쇠
- [ ] HTTP → HTTPS 리다이렉트
- [ ] (선택) SSL Labs A 등급

### 8. 핵심 E2E 시나리오

**시나리오 1: 초대 가입 → 첫 플레이**

- [ ] 초대 코드 signup
- [ ] 로그인 → 홈
- [ ] 공개 월드 선택 → 입장 캐릭터 설정
- [ ] 플레이·스트리밍 1~2턴

**시나리오 2: 카카오 (선택)**

- [ ] 카카오 로그인 → `/oauth/callback` → `/my`

**시나리오 3: 월드 생성 + AI 이미지**

- [ ] 간편 모드 — NPC `major` / `personality` / `background` ([`NPC_CHARACTER_AUTHORING_STRATEGY.md`](NPC_CHARACTER_AUTHORING_STRATEGY.md) Phase A)
- [ ] AI 커버·NPC 초상 → 저장 → 마이페이지 확인

**시나리오 4: 모바일 PWA**

- [ ] 반응형·홈 화면 추가·standalone·키보드

**시나리오 5: 비용 방어**

- [ ] 턴 쿼터 429 (한국어)
- [ ] 이미지 쿼터 429
- [ ] `EMERGENCY_SHUTDOWN=true` → 503

### 9. 모니터링

- [ ] Sentry → Slack
- [ ] Anthropic / Replicate / 호스팅 비용 알림
- [ ] (선택) UptimeRobot 등

### 10. 운영 도구

- [ ] DB/SQL 또는 관리 조회 경로
- [ ] 초대 코드 발급
  ```bash
  poetry run python backend/scripts/create_invite_code.py BETA-001 --max-uses 1
  ```
- [ ] 공식 월드 시드 ([`DEPLOYMENT.md`](DEPLOYMENT.md) §12)
  ```bash
  poetry run python backend/scripts/seed_official_worlds.py
  # Docker: docker compose exec -T -e PYTHONPATH=/app api poetry run python backend/scripts/seed_official_worlds.py
  ```
- [ ] 운영자 테스트 계정 1개

### 11. 사용자 안내

- [ ] 베타 안내 (`/welcome` 또는 모달)
- [ ] 이용약관·개인정보 처리방침
- [ ] 피드백 폼 링크
- [ ] (선택) FAQ

---

## 🟢 P2: 베타 운영 중

### 12. 일상·주간 체크

- [ ] 매일: Sentry·비용·가입·Slack
- [ ] 매주: 피드백·인기 월드·개선 우선순위

### 13. 점진적 확장

- Week 1 ~10–20명 → Week 2 ~50명 → Week 3–4 ~100명 (비용·쿼터 모니터링)

### 14. 개선 사이클

문제 → 가설 → 작은 PR → 테스트 → 배포 → 30분 모니터링 → 1주 측정

### 15. 백업

- [ ] DB 일일 자동 + 주 1회 수동
- [ ] R2 내구성 (별도 백업은 장기 검토)
- [ ] GitHub `main` + 태그 (`v0.1.0-beta`)

---

## ⚠️ 위험 시나리오 + 대응

| 시나리오 | 즉시 조치 |
|----------|-----------|
| **A 비용 폭증** | `EMERGENCY_SHUTDOWN=true` → 재시작 → 원인(봇/버그/트래픽) |
| **B 크리티컬 버그** | 이전 이미지 롤백 → Sentry → 수정 재배포 |
| **C 보안** | `JWT_SECRET` 교환·API 키 재발급·강제 로그아웃 |
| **D 외부 장애** | status.anthropic.com / replicate 상태 → 사용자 안내 |

---

## 📊 베타 KPI (참고)

- 가입 전환 50%+ · 첫 플레이 70%+ · D1 30%+ · D7 15%+
- 5xx <1% · 평균 응답 <3초 · 사용자당 월 비용 <$0.50 목표

---

## 📝 문서 링크

- [ ] [`DEPLOYMENT.md`](DEPLOYMENT.md)
- [ ] [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md)
- [ ] [`WORLD_VISUAL_AI_ROADMAP.md`](WORLD_VISUAL_AI_ROADMAP.md)
- [ ] [`NPC_CHARACTER_AUTHORING_STRATEGY.md`](NPC_CHARACTER_AUTHORING_STRATEGY.md)
- [ ] [`DEVELOPMENT.md`](../DEVELOPMENT.md)
- [ ] [`.env.example`](../.env.example)

---

## 🎯 배포 D-Day (요약)

**오전:** pull → env → migrate → build → deploy → health/HTTPS  
**오후:** E2E 5종 → 운영자 테스트 → 초대 코드 → 소규모 초대 → 모니터링  
**다음날:** 메트릭·이슈·확장 여부

---

## 💡 성공 마인드셋

완벽한 출시보다 **빠른 베타 → 피드백 → 점진 확장**. 배포는 끝이 아니라 시작.

---

**최종 업데이트:** 2026-05-27  
**다음 검토:** 베타 시작 후 1주
