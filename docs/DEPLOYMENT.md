# 프로덕션 배포 가이드 (Epic B)

베타 실행 계획은 [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md) Epic B와 [`UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md) §6·§7(비밀·Docker·배포 원칙)과 맞춘다.

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

Docker로 띄울 때는 `docker-compose.yml`의 로컬 DB URL을 **배포 환경 변수로 덮어쓴다.**

## 4. 이미지·마이그레이션

- API: `docker/Dockerfile.api` — 엔트리에서 `alembic upgrade head` 후 `uvicorn`.
- 웹: `frontend/Dockerfile` — 빌드 산출물 + Nginx(`nginx.conf`에서 `/api` 프록시). 배포 시 API 호스트명을 **실제 백엔드 URL**에 맞게 수정해야 할 수 있다(compose는 서비스명 `api` 사용).

## 5. 가입 게이트 (초대 코드)

- **의미:** `REQUIRE_INVITE_CODE_FOR_SIGNUP=true`일 때 **신규 `signup`만** 유효한 `invite_codes` 행이 있어야 한다. 이미 가입한 계정의 **로그인**에는 초대 코드가 필요 없다.
- DB 마이그레이션 `0005` 후 예시:  
  `poetry run python backend/scripts/create_invite_code.py BETA-ABC --max-uses 10`
- `MAX_TOTAL_USERS`로 전체 계정 수 상한을 둘 수 있다(미설정이면 무제한).

## 6. CI

GitHub Actions에서 Docker 이미지 빌드만 검증한다(푸시 시 자동 배포는 별도 workflow·시크릿이 필요하다).
