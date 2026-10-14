# Living World Engine — 설계 결정·트레이드오프·한계

> README를 보완하는 정리입니다. 수치는 저장소에서 재현할 수 있는 것만 적습니다.

## 한 줄

**LLM 출력을 신뢰하지 않는 입력으로 다루는 검증·비용 통제 백엔드** — AI 대화형 RPG를 테스트베드로 구현 (1인 풀스택: FastAPI · PostgreSQL/Alembic · React/TypeScript · Claude Tool Use)

---

## 설계 결정과 근거

| 결정 | 이유 | 코드·근거 |
|------|------|-----------|
| 상태 변경은 `update_game_state` 툴 제안으로만 받고, Validator를 통과한 항목만 반영 | 자유 텍스트 파싱보다 구조화 JSON이 검증 가능하고 디버깅이 쉬움 | `engine/llm.py`, `engine/validator.py` |
| Validator는 형식이 틀린 항목만 버리고 예외를 던지지 않음 (숫자 문자열은 정수로 변환) | LLM이 필드 하나를 잘못 내도 턴 전체가 실패하지 않게 | `engine/validator.py`, `tests/unit/test_validator.py` |
| 일일 턴 쿼터 = `turn_count < limit` 조건부 `UPDATE` 한 문장 + 실패한 턴은 되돌림 | SELECT로 검사하고 나중에 +1 하면 동시 요청이 함께 통과해 한도를 넘음 | `services/turn_quota.py`, `tests/unit/test_atomic_counters.py` (SQLite·PostgreSQL) |
| 비용 집계는 `cost_usd = cost_usd + :delta` 로 DB 안에서, 금액 컬럼은 `Numeric(12,6)` | 파이썬에서 읽고-더하고-쓰면 동시 갱신이 유실되고, float는 누적 오차가 생김 | `services/platform_cost.py`, `migrations/versions/0016_money_columns_numeric.py` |
| 턴 비용 = `usage`의 입력·출력·캐시 쓰기·캐시 읽기 토큰 × 각 단가 | Anthropic `input_tokens`는 캐시 토큰을 이미 제외한 값 (총 입력 = 세 입력 필드의 합) | `utils/usage_tracker.py`, `tests/unit/test_usage_tracker.py` |
| 레이트 리밋은 라우트 데코레이터 아래에 `@limiter.limit`, 429 회귀 테스트 | 순서가 반대면 slowapi 한도가 조용히 무시됨 | `api/limiter.py`, `tests/unit/test_rate_limit.py` |
| LangChain 미사용, Anthropic SDK 직접 호출 | 요청·응답·툴 흐름을 직접 보고 제어하기 위해 (대신 보일러플레이트를 직접 유지) | `engine/llm.py` |
| 사용자 키(BYOK) 대신 플랫폼 단일 키 + 일일 턴 쿼터 | 베타 정책을 서버 키 하나로 정하고 비용은 턴 쿼터로 통제. 키 컬럼을 추가했다가(`0007`) 제거(`0009`) | `docs/BETA_DEV_EXECUTION.md` Epic G |

---

## 한계

- **LLM 비용은 알림만:** 일일 추정 비용이 임계를 넘으면 웹훅 알림을 보낼 뿐 호출을 자동으로 막지 않습니다. 플레이 중단은 운영자가 `EMERGENCY_SHUTDOWN=true`로 수동 실행합니다. (이미지 생성만 일 예산 초과 시 429로 차단)
- **이미지 생성 예산·월 쿼터는 검사 후 기록:** 턴 쿼터와 달리 원자적 예약이 아니라서, 동시 요청이 몰리면 소폭 초과할 수 있습니다.
- **LoopDetector 비활성화:** 반복·정체 감지(심각도 0~10)는 구현·테스트돼 있지만, 오탐 이력 때문에 게임 루프에서 꺼 두었습니다.
- **Canon Flags는 프롬프트 수준 억제:** 확정 사실을 매 턴 주입하지만 LLM이 모순된 서사를 쓸 가능성은 남습니다. (상태 값 자체는 Validator를 거쳐서만 바뀜)
- **레이트 리밋 카운터는 프로세스 메모리:** API 워커·인스턴스가 여럿이면 각자 따로 셉니다. 수평 확장 시 Redis 같은 공유 저장소가 필요합니다.
- **장기 기억 검색은 키워드·태그 매칭 점수 방식:** 벡터 검색이 아니며, 기억 목록은 세션의 `play_sessions.payload`(JSON 컬럼)에 통째로 저장됩니다.
- **턴당 비용 측정치 없음:** `UsageTracker`로 기록하지만, 재현 가능한 측정 데이터가 저장소에 없어 비용 수치는 주장하지 않습니다.

---

## 재현

```bash
# 유닛 + 스모크 (CI와 동일, 실제 API 불필요) — 382 passed
poetry run pytest backend/tests -m "not integration and not e2e" --no-cov -q

# 턴 쿼터·비용 집계 동시성 테스트를 PostgreSQL에서도 (임시 스키마를 만들고 지움)
LWE_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:5432/living_world_test \
  poetry run pytest backend/tests/unit/test_atomic_counters.py --no-cov -q
```

실행 방법은 [README](../README.md#-실행-방법)를 참고하세요.
