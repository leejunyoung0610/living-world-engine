# AI 이미지 저장 (커버·NPC 초상)

## 왜 사진이 안 보이나

1. **Replicate 임시 URL 만료**  
   AI 생성 직후 `replicate.delivery` 등 임시 HTTPS 주소가 DB에 저장됩니다. 이 주소는 **며칠~수주 후 404**가 됩니다. DB에는 URL이 남아 있어도 브라우저·앱에서는 빈 썸네일처럼 보입니다.

2. **R2(Cloudflare) 미설정**  
   `.env`에 `R2_*` 다섯 값이 없으면 서버가 Replicate URL을 **그대로** 저장합니다 (`backend/src/services/r2_storage.py`). 영구 미러는 스킵됩니다.

3. **UI**  
   홈·탐색 카드는 이미지 로드 실패 시 썸네일을 숨깁니다. “이미지가 없는 월드”처럼 보일 수 있습니다.

## 이미지를 유지하려면

### 운영(권장)

`.env` 또는 `.env.production`에 다음을 모두 설정합니다 (예시는 `.env.production.example`):

| 변수 | 설명 |
|------|------|
| `R2_ACCOUNT_ID` | Cloudflare 계정 ID |
| `R2_ACCESS_KEY` | R2 API 토큰 Access Key |
| `R2_SECRET_KEY` | R2 API 토큰 Secret |
| `R2_BUCKET` | 버킷 이름 |
| `R2_PUBLIC_URL` | 버킷 공개 도메인 (커스텀 도메인 또는 r2.dev) |

설정 후 **API 컨테이너/프로세스 재시작** → 이후 AI 생성분은 R2에 업로드되고 **영구 공개 URL**이 DB에 저장됩니다.

확인:

```bash
curl -s http://localhost:8000/api/worlds/meta/image-storage | jq
# permanent_storage: true 이면 OK
```

### 이미 만료된 URL

- DB에 남은 Replicate URL은 **복구 불가**입니다.
- 월드 편집 → **AI 커버 / AI 초상**으로 다시 생성하세요 (R2 설정 후 생성하면 재만료를 막을 수 있음).

### 로컬 개발

- R2 없이도 Replicate로 **테스트 생성**은 가능합니다. 다만 URL은 곧 만료됩니다.
- 실제 UGC 데이터는 `docker-compose.yml`의 `DATABASE_URL`이 가리키는 Postgres를 사용하는지 확인하세요 (`host.docker.internal` = Mac 로컬 DB).

## 코드 경로

- 생성: `POST /api/worlds/{id}/generate-cover`, `POST .../npcs/{npc_id}/generate-portrait`
- 미러: `mirror_generated_cover_to_permanent_url`, `mirror_npc_avatar_to_permanent_url`
- 메타: `GET /api/worlds/meta/image-storage` — 에디터 배너용

## 체크리스트

- [ ] 프로덕션 `.env`에 R2 5종 설정
- [ ] `permanent_storage: true` 확인
- [ ] 만료된 월드는 소유자가 AI 재생성
- [ ] 베타 배포: `docs/BETA_DEPLOYMENT_CHECKLIST.md` P0 env 항목과 함께 점검
