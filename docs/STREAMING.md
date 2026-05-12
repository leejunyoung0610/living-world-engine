# 플레이 스트리밍 (SSE) — 작업 문서

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-05-10 |
| 상태 | **PR-1 완료 / 실사용 중** |
| 관련 문서 | `PRODUCTION_ROADMAP.md` · `BETA_DEV_EXECUTION.md` · `ARCHITECTURE.md` |
| 관련 코드 | `backend/src/engine/llm.py`, `backend/src/engine/game_loop.py`, `backend/src/api/routes/play.py`, `frontend/src/api/play.ts`, `frontend/src/pages/PlayPage.tsx`, `frontend/src/utils/dialogueSplit.ts` |

---

## 1. 결정 — 옵션 A (텍스트 우선 스트리밍)

| 옵션 | 동작 | 채택 이유 |
|------|------|-----------|
| **A. 텍스트 우선** *(채택)* | 1차 LLM 호출만 stream. tool_use 텍스트 fallback(2차 호출)은 비스트림. | Single-Pass 가 기본값이라 거의 모든 턴에서 1차 응답에 NPC 대사가 함께 옴 → 사용자 체감은 "글자가 항상 흐름". 구현 단순 + 6주 일정상 유리. |
| B. 항상 스트림 | 1차도 2차도 다 stream. | 2차 호출 자체가 본질적으로 멍 발생. 일관성보다 단순성을 우선. |
| C. Single-Pass 강제 | 1차에 텍스트 없으면 placeholder 후 2차. | 응답 스타일이 미세하게 변할 수 있어 회귀 위험. |

---

## 2. 흐름

```
[유저 입력]
   │
   ▼
POST /api/play/{id}/turn/stream                      ← play.py
   │ (사전: 인증·세션·긴급셧다운·LLM 키·턴 쿼터 사전 체크)
   │
   ▼
GameEngine.process_turn_stream(msg)                  ← game_loop.py
   │ memory 검색 → system_prompt 빌드 → context_manager
   ▼
ClaudeClient.process_turn_stream(...)                ← llm.py
   │ client.messages.stream(...) 1차 호출
   │   text_delta → yield {"type":"delta","text":...}
   │   tool_use 입력은 누적
   │ stop_reason == "tool_use" 이고 텍스트 없음 → 비스트림 2차 호출 (_handle_tool_use)
   │ 그 외 → done 으로 결과 반환
   ▼
GameEngine._finalize_turn_after_llm()
   │ usage 적산 → state_changes 적용 → advance_turn → 메모리 추가
   │ 이벤트 체크 (cap 적용) → tick_cooldowns
   │ conversation_history 갱신
   ▼
SSE 종료 시점에:
   ├─ turn_quota.record_platform_turn (쿼터 차감)
   ├─ platform_cost.record_platform_cost_delta
   ├─ _persist_session (DB 영속화)
   └─ event: done {turn, day, response, response_segments, events_triggered}
```

---

## 3. SSE 프로토콜

```
event: delta
data: {"text": "엘레나는 가만히 책을"}

event: delta
data: {"text": " 덮으며 너를 본다."}

event: done
data: {"turn":12,"day":3,"response":"...","response_segments":[...],"events_triggered":[]}
```

에러 시:
```
event: error
data: {"detail": "..."}
```

응답 헤더:
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

---

## 4. 점진 화자 분할 (`dialogueSplit.ts`)

스트리밍 중에도 NPC 별 박스로 구분되도록 클라이언트에서 누적 텍스트를 매 델타마다 화자 블록으로 분할.

- 알고리즘은 백엔드 `backend/src/engine/dialogue_split.py` 와 100% 동일 (빈 줄 분할 + 첫 줄로 NPC 매칭, 나머지는 "내레이션").
- `GET /api/play/{id}/history` 응답에 `npc_names: list[str]` 추가 — 클라이언트가 분할에 사용.
- `done` 시점에 서버가 보낸 정확한 `response_segments` 로 마지막 한 번 더 교체 (분할 가장자리 케이스 대비).

---

## 5. 안전장치

| 영역 | 처리 |
|------|------|
| 인증 / 세션 / 권한 | 스트림 시작 *전* 단계에서 401 / 404 / 403 일반 HTTPException — SSE 시작 후 거부 안함 |
| 긴급 셧다운 (`emergency_shutdown`) | 시작 전 503 |
| 플랫폼 LLM 키 미설정 | 시작 전 503 |
| 일일 턴 쿼터 | 시작 전 *체크*, 종료 시점에 *기록*. 중도 끊김 시 사용자 보호. |
| 일일 비용 초과 | 종료 시점에 `record_platform_cost_delta` 로 누적 |
| LLM/엔진 예외 | `event: error` SSE 로 전달, 클라이언트는 placeholder 제거 |
| 클라이언트 abort | 서버 측 generator 가 끊기는 시점에 자연 종료 (이미 차감 안 됨) |

---

## 6. 단위 테스트

`backend/tests/unit/test_api_play_stream.py` — 4 케이스:
1. SSE 헤더 + delta(여러 청크) → done(turn/day/response/segments/events) 순서
2. 인증 없으면 401 (스트림 시작 전)
3. 모르는 세션 ID → 404
4. 다른 유저 → 404 (404 위장으로 권한 정보 누설 방지)

`backend/tests/unit/test_api_play_regenerate.py` — 재생성 스트림 정상(히스토리 2개 유지), **편집 재생성** 시 히스토리 user 내용 갱신, 체크포인트 없을 때 409, 401.

전체 테스트 217+ passed (스트림·재생성 포함).

---

## 7. PR-2 — 마지막 응답 재생성 (`/turn/regenerate/stream`)

| 항목 | 내용 |
|------|------|
| 엔드포인트 | `POST /api/play/{session_id}/turn/regenerate/stream` (선택 JSON 본문, SSE 프로토콜은 `/turn/stream` 과 동일) |
| 본문 | 생략 또는 `{}` — 직전 플레이어 대사 그대로 재실행. `{"message":"..."}` — **마지막 플레이어 대사를 이 문자열로 바꾼 뒤** 같은 스냅샷에서 `process_turn_stream` 재실행. |
| 동작 | 직전 완료 턴 **시작 시점** 스냅샷(`regenerate_checkpoint`)으로 `WorldState`·대화·이벤트 쿨다운·LTM 메모리·**usage_tracker** 를 복원한 뒤, 위 `message`(또는 직전 사용자 메시지)로 `process_turn_stream` 재실행. |
| 스냅샷 시점 | 매 `/turn`·`/turn/stream` 요청이 **LLM 호출 전** `export_play_payload(engine)` 로 갱신; `play/start` 직후에도 초기 스냅샷 저장. DB `payload.regenerate_checkpoint` 에 같이 영속화. |
| 제약 | 마지막 교환이 `user` 다음 `assistant` 가 아니면 422. 체크포인트 없음(구 세션 등)이면 **409**. |
| 쿼터·비용 | 일반 턴과 동일 — 재생성도 턴 1회·API 비용 델타 1회. |
| 프론트 | `PlayPage` 상단 「다시 생성」 / 「대사 수정」(시트에서 편집 후 스트림) — 마지막 **본문** assistant 만 대상(`[이벤트]` 줄은 건너뜀). |

---

## 8. 베타 진입까지 다음 PR

| # | 작업 | 예상 |
|---|------|------|
| **PR-3 편집/삭제** | 마지막 사용자 메시지 **편집 → 재생성**(API·UI). 메시지 단위 삭제는 미구현. | 1일 |
| **PR-4 페르소나 저장** | `personas` 테이블 + CRUD + PlaySetupPage 드롭다운. 매번 폼 입력 제거. | 1.5일 |
| **베타 안내 페이지** | 친구 30명용 안내 / 피드백 폼 / 메트릭 핀포인트 | 0.5일 |

---

## 9. 변경 로그

- 2026-05-10 — PR-1 완료. 옵션 A 채택. 점진 화자 분할 추가 (사용자 요청). 휴대폰 (`http://172.16.100.133:8080`) 에서 NPC 별 박스 흐름 확인.
- 2026-05-12 — **PR-3 (일부)** 재생성 `POST` 에 선택 `message` 본문 + Play UI 「대사 수정」 모달/시트.
- 2026-05-10 — **PR-2** `regenerate_checkpoint` + `POST .../turn/regenerate/stream` + Play UI 「다시 생성」.
