# 실서비스 전환 — 가치 기준 갭 분석 & 개발 계획

이 문서는 저장소 코드·[`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md)·[`DEPLOYMENT.md`](DEPLOYMENT.md)를 기준으로, **“베타로 쓸 만한 기능”**과 **“사용자가 돈·데이터·시간을 맡길 만한 서비스”** 사이의 차이를 정리하고 우선순위별 로드맵을 제시한다.

---

## 1. 이미 갖춘 것 (실서비스 가치에 기여하는 부분)

| 영역 | 내용 | 코드·문서 위치 |
|------|------|------------------|
| 멀티 유저·세션 | JWT, 유저별 플레이 세션, 월드 소유·공개 탐색 | `auth.py`, `play.py`, `worlds.py` |
| UGC 월드 | CRUD, 공개 범위, 계정당 상한 | `worlds.py`, `WorldEditorPage.tsx` |
| 비용·남용 방어 (플랫폼 키) | 일일 턴 쿼터(PostgreSQL), 일일 추정 비용·웹훅, 긴급 셧다운 | `turn_quota.py`, `platform_cost.py`, `config.py` |
| 보안 최소선 | CORS 프로덕션 검사, slowapi(일부), 보안 헤더, `/health` DB ping | `security.py`, `limiter.py`, `main.py` |
| 관측 기초 | Sentry(선택), JSON 액세스 로그, `X-Request-Id` | `main.py`, `request_context_middleware.py`, `logging_setup.py` |
| 배포 형태 | Docker API/웹, Alembic 마이그레이션, compose | `docker/`, `migrations/` |

이 레이어는 **“소규모 유료·초대제 서비스”**의 뼈대로는 이미 의미가 있다.

---

## 2. 부족한 것 — 실서비스 가치 관점에서 묶음

### 2.1 신뢰·계정 (Trust)

- **이메일 인증** 없음 — 가입 즉시 계정 활성, 스팸·부정 가입 대응 약함 (`User` 모델에 검증 필드 없음).
- **비밀번호 재설정** 없음 — 실사용자 이탈·CS 비용 증가.
- **계정 삭제 / 데이터 내보내기** 없음 — 실서비스·일부 법역에서 기대치 상승.
- **OAuth(카카오 등)** 없음 — 국내 B2C 전환에 유리하지만 필수는 아님; **별도 Epic**.

### 2.2 법·정책 (Compliance, Epic J와 정렬)

- 프론트에 **이용약관·개인정보처리방침** 정적 라우트·가입 동의 흐름 없음.
- **유료 전환 시**: 청약철회·환불·유료 약관, **해외 LLM 전송** 고지 정리 필요 ([`UGC_MVP_PLAN.md`](UGC_MVP_PLAN.md)와 정책 정본 연동).

### 2.3 수익 (Revenue)

- **결제·구독·크레딧** API·DB 없음 — PG 연동, 웹훅 멱등, 구독 상태, 영수증·환불 플로우 전부 신규 도메인.

### 2.4 운영·확장 (Ops)

- **DB/볼륨 백업·복구** — 코드가 아니라 **운영 절차 + 검증**이 문서·자동화로 필요.
- **다중 API 인스턴스** 시 `data/play_sessions/*.json` 등 **파일 기반 LTM**과 DB 스냅샷 일관성 — 스케일 전략(공유 스토리지 vs DB 단일화) 결정 필요.
- **리버스 프록시 뒤 레이트리밋**: `get_remote_address` 기준이 프로덕션에서 왜곡될 수 있음 — `X-Forwarded-For` 정책 또는 trusted proxy 설정.
- **관측 심화**: Sentry/로그 외 **메트릭·대시보드**(턴 수, 5xx, LLM 실패율, P95 지연)는 아직 앱에 없음.

### 2.5 남용 방어 세부 (Security)

- **월드 API**(`worlds.py`)에 slowapi **미적용** — 탐색/CRUD 남용 시 부하 가능.
- **플레이 API**: `@limiter`는 **`POST .../turn`** 위주; `start`, `sessions`, `history`, `DELETE` 등은 한도 약함.
- **보안 헤더**: CSP, HSTS, Permissions-Policy 등은 미도입(선택 과제).

### 2.6 품질 보증 (QA)

- **HTTP E2E 체인**(가입 → 월드 → start → turn) — [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md) Epic I **미완**.
- 기존 `backend/tests/e2e/` 는 **엔진 + 실 API 키** 성격에 가깝고, API 스모크와 역할이 다름.
- **CI**: Docker 빌드 워크플로만 있고 **`pytest` 게이트 없음**.

### 2.7 제품 UX (차별화·전환)

- 월드 생성이 **JSON 편집 중심** — 일반 사용자 전환율·완성도 한계. (논의한 **3트랙**: 정교 폼 / 자유 서술→JSON / 단계별 자동 생성)

### 2.8 제품·성장 (선택)

- **관리자 콘솔** 없음 — 초대 코드·유저 정지·공지는 스크립트/SQL 의존.
- **분석**(퍼널·리텐션) — Sentry/비용 웹훅과 별개; Posthog 등은 미연동.

---

## 3. 개발 계획 (단계 + 우선순위)

아래는 **의존성과 리스크**를 기준으로 한 제안 순서다. 병행 가능한 항목은 같은 페이즈에 묶었다.

### Phase A — “돈을 받기 전에 반드시” (4–8주 규모 가이드)

| ID | 작업 | 산출물 / DoD |
|----|------|----------------|
| A1 | 법무 최소 (Epic J) | 프론트 `/terms`, `/privacy` + 가입 시 링크·동의 체크박스(필요 시) |
| A2 | 계정 신뢰 | 이메일 인증 플로(토큰·만료) 또는 “실서비스 출시 전까지 이메일 검증 필수” 정책 명시 |
| A3 | 계정 복구 | 비밀번호 재설정(토큰 메일 — SendGrid 등 SMTP 또는 Resend) |
| A4 | 배포 신뢰 (Epic B) | 프로덕션 HTTPS, 환경 변수, `alembic upgrade head` 검증 |
| A5 | API 스모크 (Epic I) | `backend/tests/smoke/test_user_journey.py` + `@pytest.mark.smoke` |
| A6 | CI 게이트 | [`.github/workflows/pytest.yml`](../.github/workflows/pytest.yml) — `pytest -m "not integration and not e2e"` |
| A7 | 레이트리밋 보강 | `worlds` 탐색·CRUD, `play/start`·`history` 등에 합리적 한도; 프록시 IP 처리 |
| A8 | 백업 런북 | PostgreSQL 스냅샷 주기 + 복구 리허설 1회 문서화 |

**가치:** 이탈 감소, 장애·분쟁 시 설명 가능, 릴리스 회귀 방지.

### Phase B — “유료·성장 직전”

| ID | 작업 | 산출물 / DoD |
|----|------|----------------|
| B1 | 계정 생명주기 | 계정 삭제(API + 연쇄 삭제 world/session/파일 정책); 선택적 데이터 Export JSON |
| B2 | 결제 v0 | PG 1곳 + 단일 상품(예: 월 구독 또는 크레딧 팩); 웹훅 검증·멱등 키 |
| B3 | 쿼터/결제 연동 | 유료 플랜에 따른 `PLATFORM_DAILY_TURN_LIMIT` 또는 별도 크레딧 테이블 |
| B4 | 관리 최소 | 초대 코드·유저 조회 스크립트를 넘어선 간단 admin(역할 플래그 또는 내부 도구) |
| B5 | 옵저버빌리티 | LLM/5xx/턴당 지연 메트릭(최소: 로그 기반 대시보드 또는 호스트 메트릭) |

**가치:** 매출 가능, 운영 비용 통제, CS 반복 작업 감소.

### Phase C — “차별화·전환율” (월드 3트랙)

| ID | 작업 | 산출물 / DoD |
|----|------|----------------|
| C1 | 정교 트랙 | 스키마 맞는 폼/위저드 → 기존 `WorldCreateBody` JSON 생성 |
| C2 | 자유 서술 트랙 | LLM + JSON Schema + 서버 `_validate_payload` + 실패 시 재시도·수동 편집 |
| C3 | 자동 트랙 | 멀티턴 질문 세션 → 최종 JSON; v1은 질문 5~7개 고정 선택지 권장 |
| C4 | Epic K 정리 | 세션 공유 `/play/{id}` 정책 문구·UI (소유자만 이어하기 등) |

**가_value:** “챗봇”이 아니라 **UGC·세계 창작**으로 인지되게 함.

### Phase D — “스케일·한국 시장 옵션”

| ID | 작업 |
|----|------|
| D1 | 카카오(또는 1종) OAuth + 계정 연동 정책 |
| D2 | LTM/스냅샷 스토리지 단일화(다중 워커·K8s 대비) |
| D3 | CSP·HSTS 등 보안 헤더 고도화 |

---

## 4. 권장 타임라인 (압축)

| 기간 | 초점 |
|------|------|
| 1–2주 | A4, A5, A6, A7 일부 — **배포·테스트·남용 방어** |
| 3–6주 | A1–A3, A8 — **법무·계정·백업** |
| 7–12주 | B1–B3 — **삭제·결제·요금제** |
| 병행 | C1–C3 점진 롤아웃 — **월드 생성 3트랙** |

숫자는 팀 규모에 따라 조정; **Phase A는 유료 전에**, **Phase B는 첫 결제와 동시에** 맞추는 것이 안전하다.

---

## 5. 의도적 비후순위 (초기에 안 해도 되는 것)

- 완전한 GDPR 로그 기록·DPO 프로세스(시장·매출 규모에 따라).
- 마이크로서비스 분해, 자체 추천 ML.
- 월드 에디터 실시간 협업.

---

## 6. 문서 연동

- 베타 체크리스트: [`BETA_DEV_EXECUTION.md`](BETA_DEV_EXECUTION.md) — Epic B, I, J, K와 위 Phase를 **1:1로 갱신**할 것.
- 배포: [`DEPLOYMENT.md`](DEPLOYMENT.md) — 백업·모니터링 절을 Phase A8/B5와 맞출 것.

---

*마지막 갱신: 코드베이스 스냅샷 기준. 우선순위는 사업 우선(국내 vs 해외, B2C vs 크리에이터)에 맞게 조정하라.*
