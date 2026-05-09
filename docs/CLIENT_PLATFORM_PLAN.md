# 클라이언트 플랫폼 강화 계획 — Kakao OAuth + PWA + 반응형

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-05-10 |
| 상태 | **A·B·C 구현 완료 (운영 키 주입 + QA 대기)** |
| 범위 | 카카오 소셜 로그인, PWA(설치 가능 웹앱), 모바일 우선 반응형 UI |
| 비범위 | iOS/Android 네이티브 앱(스토어 배포), 앱 내 결제, 푸시 알림(추후) |
| 관련 문서 | `STAT_DRIVEN_EVENTS.md`, `UGC_MVP_PLAN.md` |

---

## 0. 결론 요약

| 단계 | 묶음 | 1줄 |
|------|------|-----|
| **A** | **반응형 UI 정비** | 모바일 화면에서 깨지는 곳부터 손보고 토큰화. PWA·OAuth 진입점이 모바일이라 선행. |
| **B** | **PWA 셸** | manifest, 서비스 워커(오프라인 셸), 설치 프롬프트, 안전한 캐시 전략. |
| **C** | **Kakao OAuth** | 백엔드 콜백 + JWT 발급 통합, 프론트는 "카카오로 시작" 버튼. |
| **D** | **운영 보강** | iOS PWA 메타, 푸시·공유, 분석. |

A → B → C 가 순서. **A를 안 하면 B/C에서 모바일 UX가 무너진다.**
실제 PR 단위는 §5 표 참고.

---

## 1. 왜 이 순서인가

- **PWA(설치형 웹앱)는 결국 휴대폰**. 데스크톱 디자인만 잘 돼 있으면 인스톨하자마자 좁은 화면에서 깨진다 → **반응형 먼저**.
- **Kakao OAuth**는 모바일에서 압도적으로 가치가 있다(카톡 in-app 브라우저). 그러니 PWA가 먼저 정돈되어야 깔끔하다.
- 백엔드 변경은 **C 단계에서 한 번 크게** 일어나므로(소셜 ID 컬럼·콜백) UI 작업과 충돌이 적게 묶을 수 있다.

---

## 2. 단계 A — 반응형 UI 정비

### 2-1. 현재 상태(스냅샷)

- Tailwind 기준, 대부분 컨테이너가 `max-w-3xl` / `max-w-4xl` / `max-w-lg`로 데스크톱 폭에 맞춰져 있음.
- `LoggedInNav`, `MyPage`, `ExplorePage`, `WorldEditorPage`, `PlaySetupPage`, `PlayPage` 모두 한 번씩 좁은 폭에서 점검 필요.
- 입력·텍스트에어리어 다수 — 모바일 가상 키보드와 충돌(스크롤 점프) 점검 필요.

### 2-2. 작업 항목

1. **레이아웃 토큰 정리** — `container` / `page-shell` / `card` 클래스를 `frontend/src/styles/`에 헬퍼로 추출. 각 페이지 고유의 한정 너비 제거하고 공유.
2. **네비게이션 모바일화** — `LoggedInNav`에 햄버거(작은 화면) 토글 추가, 큰 화면은 그대로.
3. **폼 모바일 보정** — 라벨·입력 사이 간격, `inputMode`, `autoComplete`, `enterkeyhint` 정비. iOS 줌 방지를 위해 입력 폰트 ≥ 16px.
4. **`PlayPage` 메시지 영역** — 가상 키보드 올라올 때 입력창 가려지지 않도록 `flex` + `dvh` 단위 사용. 메시지 정렬·말풍선 폭 모바일 케이스 점검.
5. **에디터 페이지** — `WorldEditorPage`의 좌우 두 컬럼은 좁은 화면에서 1컬럼으로 떨어지게.
6. **다크 모드 색·대비** — WCAG AA에 가깝게(특히 placeholder, 보조 텍스트).
7. **상태 메시지·로딩** — 모바일에서 길어지는 텍스트 line-clamp 통일.
8. **회귀 방지 스냅샷** — 주요 페이지에서 (320 / 390 / 768 / 1280)px 4종 스크린샷 비교(eyeball 충분, 자동화 미정).

### 2-3. 완료 조건(DoD)

- iPhone SE 폭(320px)부터 데스크톱(1440px)까지 **레이아웃이 깨지지 않음**.
- 모든 페이지에서 **스크롤만으로** 모든 액션이 가능 (가로 스크롤 없음).
- `PlayPage`에서 모바일 키보드 올라와도 입력창이 화면 안에 남는다.

---

## 3. 단계 B — PWA 셸

### 3-1. 추가물

- `frontend/public/manifest.webmanifest` — name, short_name, theme_color, background_color, display=`standalone`, icons(192/512, maskable).
- `frontend/public/icons/` — 앱 아이콘 세트 (디자인은 임시로 단색 + 글자, 추후 교체).
- 서비스 워커: **`vite-plugin-pwa`** 도입(권장). 캐시 전략은:
  - 정적 자산: `precache`.
  - `/api/*`: **NetworkOnly** 또는 **NetworkFirst(짧은 timeout)** — 토큰 만료·세션 일관성 우선.
  - 이미지: `StaleWhileRevalidate`.
- `index.html`에 모바일 메타 보강 — `theme-color`, `apple-mobile-web-app-capable`, `apple-touch-icon`, `viewport-fit=cover`.
- 인스톨 안내 — `beforeinstallprompt` 리스너, "홈 화면에 추가" 토스트(데스크톱은 1회만 노출).
- 오프라인 셸: 네트워크가 끊겼을 때 단순 안내 페이지(채팅은 온라인 필요).

### 3-2. 보안·캐시 주의

- 토큰은 **localStorage** 그대로 둠(현 구조 유지). 서비스 워커에서 토큰 캐시 금지.
- API 응답은 **캐시하지 않는** 게 기본 — 멀티 디바이스에서 세션 상태 꼬임 방지.
- 새 빌드 배포 시 자동 업데이트(스킵 wait + reload).

### 3-3. 완료 조건(DoD)

- Chrome Lighthouse PWA 항목 **Installable** 통과.
- 홈 화면에 추가하면 standalone으로 뜨고, 첫 화면이 1초 안에 보임.
- 새 빌드 배포 후 1회 새로고침으로 갱신.

---

## 4. 단계 C — Kakao OAuth 로그인

### 4-1. 흐름 (Authorization Code, 백엔드 교환)

1. 프론트: "카카오로 시작" → `GET /api/auth/kakao/authorize` 로 리다이렉트.
   - 백엔드가 `state` 발급(CSRF용, 쿠키/세션) + Kakao 인가 URL로 302.
2. 카카오 → `GET /api/auth/kakao/callback?code=...&state=...`
3. 백엔드: `state` 검증 → Kakao **token** 교환 → Kakao **userinfo** 호출.
4. 백엔드: 이메일 또는 `kakao_sub`(카카오 unique id) 로 사용자 lookup/생성.
5. 자체 JWT 발급 → **프론트 콜백 페이지로 리다이렉트** (해시/쿼리에 토큰 또는 단기 코드 → 1회 교환).
6. 프론트: 토큰 저장 후 `/my`로 이동.

> 모바일 카카오톡 in-app 브라우저 호환성을 위해 **백엔드 교환 흐름**(서버사이드)을 권장. SPA-only(Implicit/PKCE)는 카카오에서 제약이 있고 웹뷰 이슈도 자주 난다.

### 4-2. 백엔드 변경

- **DB**: `users` 테이블에
  - `kakao_sub VARCHAR(64) UNIQUE NULL`
  - `auth_provider VARCHAR(16) NOT NULL DEFAULT 'local'` (`'local'` | `'kakao'`)
  - `password_hash`를 **NULLABLE**로 (소셜 가입 사용자는 비밀번호가 없을 수 있음).
  - 마이그레이션 파일 추가 (Alembic `0010_kakao_oauth.py` 가안).
- **라우트** (`backend/src/api/routes/auth.py` 또는 새 파일 `auth_kakao.py`):
  - `GET /api/auth/kakao/authorize`
  - `GET /api/auth/kakao/callback`
- **설정** (`utils/config.py`):
  - `kakao_client_id`, `kakao_client_secret`(선택), `kakao_redirect_uri`, `kakao_login_enabled` 플래그.
  - 비활성 상태에서는 라우트 자체가 404.
- **보안**:
  - `state` 쿠키 SameSite=Lax + httpOnly + Secure(prod).
  - 콜백에서 받은 토큰은 **로깅 금지** (현재 logger redaction 정책 검사).
  - 신규 가입 시 초대 코드 정책과의 관계 결정 — 옵션:
    - (a) **소셜 가입은 초대 코드 면제** (운영 단순)
    - (b) 초대 코드 필요한 경우 콜백 직후 "초대 코드 입력 페이지"로 우회.
  - **권장**: a, 단 가입 cap(`max_total_users`)는 그대로 적용.

### 4-3. 프론트 변경

- 로그인/가입 페이지에 **"카카오로 시작"** 버튼 — 클릭 시 `window.location = "/api/auth/kakao/authorize"`.
- 콜백 처리 페이지 `/oauth/callback` (or 백엔드가 직접 `/my?token=...`로 리다이렉트).
- 프로필 페이지에 **연결 상태**(Kakao 연결됨) 표시. 향후 연동 해제는 옵션.

### 4-4. 운영·테스트

- 카카오 디벨로퍼스 앱 등록, 도메인·Redirect URI(개발/운영) 등록.
- E2E 시나리오: 카카오 로그인 → JWT 받음 → `/api/auth/me` 200.
- 보안 테스트: `state` 위조·재사용·없을 때 401/400.
- 단위 테스트: 사용자 lookup/create 분기, 기존 이메일 충돌 처리.

### 4-5. 완료 조건(DoD)

- 일반 이메일 가입과 카카오 가입 사용자가 **같은 화면에서 동등하게 동작**.
- 카카오 비활성 토글에서 라우트 차단 + 프론트 버튼 숨김.

---

## 5. PR 분해 (전체)

| # | 묶음 | 작업 | 산출물 |
|---|------|------|--------|
| **PR-A1** | A | 공통 레이아웃 토큰 추출 + `LoggedInNav` 모바일 햄버거 | `styles/`, `components/` |
| **PR-A2** | A | `MyPage`, `ExplorePage`, `PlaySetupPage` 반응형 점검 | 각 페이지 |
| **PR-A3** | A | `PlayPage` 채팅 영역 + 가상 키보드 대응 (`dvh`) | `PlayPage.tsx` |
| **PR-A4** | A | `WorldEditorPage` 모바일 폼 점검 + 입력 폰트 16px | `WorldEditorPage.tsx` |
| **PR-B1** | B | `vite-plugin-pwa` 도입, manifest, 아이콘, 메타 | `vite.config.ts`, `public/`, `index.html` |
| **PR-B2** | B | 캐시 전략 + 인스톨 토스트 + 자동 업데이트 | `frontend/src/pwa/` |
| **PR-C1** | C | DB 마이그레이션(`kakao_sub`, `auth_provider`, `password_hash` nullable) | `migrations/0010_*.py`, `models/user.py` |
| **PR-C2** | C | `/api/auth/kakao/authorize`·`callback` + state 쿠키 + 사용자 lookup/create + JWT | `routes/auth_kakao.py`, `config.py`, 테스트 |
| **PR-C3** | C | 프론트 "카카오로 시작" 버튼 + 콜백 페이지 + 마이페이지 연동 표시 | `LoginPage.tsx`, `pages/OAuthCallback.tsx`, `App.tsx` |
| **PR-C4** | C | E2E 스모크 + 운영 가이드 (`docs/DEPLOYMENT.md`에 카카오 콘솔 절) | docs, smoke |
| **PR-D1** | D | iOS PWA 미세 조정(splash, status bar) + 분석 툴 후크 | `index.html`, `pwa/` |

각 PR은 머지 전 **`/health`·메인 흐름 수동 확인** 포함.

---

## 6. 일정 (가안 — 솔로·병행)

| 주차 | 묶음 | 산출 |
|------|------|------|
| **Week 1** | A | A1·A2·A3·A4 (반응형 정비 종료) |
| **Week 2** | B | B1·B2 (PWA 인스톨 가능) |
| **Week 3** | C | C1·C2 (백엔드 OAuth 통합) |
| **Week 4** | C+D | C3·C4·D1 (프론트 통합 + 운영) |

> 스탯 기반 이벤트(`STAT_DRIVEN_EVENTS.md`)는 **별 트랙**. 동시 진행 시 이 문서의 A·B는 UI 트랙, 그 사이 백엔드 시간에 이벤트 PR-1/PR-2를 끼워 진행 가능.

---

## 7. 리스크·결정 필요 항목

| 항목 | 메모 |
|------|------|
| 카카오 in-app 브라우저 | 일부 리다이렉트 차단 케이스 → 외부 브라우저 유도 안내 페이지 검토 |
| 동일 이메일 이미 가입(local) | "카카오로 로그인 시도했지만 이메일이 이미 일반 가입됨" → 안내하고 비밀번호 로그인 제안. 자동 머지는 안 함. |
| 비밀번호 nullable 후 보안 | 일반 가입 사용자는 여전히 비밀번호 필수 — 컬럼 nullable + 라우트 단에서 강제 |
| 토큰 저장 위치 | 그대로 localStorage. 추후 httpOnly 쿠키 + Refresh 도입은 별도 PR |
| PWA 캐시 vs 새 배포 | 자동 업데이트 + 한 번 강제 새로고침 — A/B 테스트 필요 시 별도 정책 |
| iOS 푸시 | iOS 16.4+에서 PWA 푸시 가능, 이번 분기 비범위 |

---

## 8. 보고서 한 줄

이번 주는 **클라이언트 플랫폼 트랙 신설**. UGC 흐름 정합 작업이 끝났으니 다음 단계로 **모바일·PWA·소셜 로그인**을 차례로 도입해, 일반 사용자가 "휴대폰에서 카카오로 1탭 가입 → 홈에 설치 → 즉시 플레이" 경로를 갖추는 게 목표.

---

## 9. 변경 로그

- 2026-05-10 — 초안 작성 (3개 묶음 정의, PR 분해, 4주 가안).
- 2026-05-10 — A·B·C 트랙 12개 PR 모두 구현·로컬 동작 확인.
  - **C1** 마이그레이션 `0010` 적용 (`auth_provider`, `kakao_sub`, `password_hash` nullable).
  - **C2** 백엔드 `/api/auth/kakao/{authorize,callback}` — state JWT 검증, Client Secret 옵션, 동일 이메일이면 자동 연결, 카카오 전용 계정의 비밀번호 로그인 차단.
  - **C3** 프론트 — 카카오 노란 버튼, `/oauth/callback`, MyPage 「카카오 연동」 배지.
  - **C4** `DEPLOYMENT.md` 갱신, 단위 테스트 17건 (auth 9 + kakao 8) + 스모크 1건 그린.
  - **부가** — Redirect URI 동적 도출(요청 호스트 기준)로 같은 빌드를 `localhost:8080`/LAN IP/운영 도메인에서 모두 사용. 리버스 프록시 헤더(`X-Forwarded-*`) 통과 + uvicorn `--proxy-headers` 적용.
  - **부가** — `backend/scripts/seed_official_worlds.py` — `worlds/<slug>/*.json` 을 「운영팀」 시스템 유저 소유의 공개 월드로 upsert(이름 매칭, `--force` 로 재생성). 기본 캠퍼스·아케인 아카데미 시드 완료.
  - **운영자 결정 대기**: 비즈 인증 후 `account_email` 「필수 동의」 전환 시점 (현재는 「선택 동의」 + 합성 메일 폴백).
