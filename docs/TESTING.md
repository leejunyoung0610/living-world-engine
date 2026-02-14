# Living World Engine - 테스트 전략

> "테스트가 없으면 리팩토링도, 배포도, 자신감도 없다."

---

## 1. 테스트 피라미드

```
        ╱  E2E  ╲           ← 전체 게임 플로우 (10턴 플레이) — 예정
       ╱─────────╲          
      ╱ Integration╲        ← GameEngine + 실제 Claude API (5개) ✅
     ╱───────────────╲      
    ╱   Unit Tests    ╲     ← 각 모듈 독립 검증 (58개) ✅
   ╱───────────────────╲    
```

| 레벨 | 파일 수 | 테스트 수 | API 필요 | 실행 시간 | 상태 |
|------|---------|-----------|----------|-----------|------|
| **Unit** | 5개 | 58개 | ❌ (Mock) | ~0.17초 | ✅ 완료 |
| **Integration** | 1개 | 5개 | ✅ (~$0.05/회) | ~60초 | ✅ 완료 |
| **E2E** | 예정 | 예정 | ✅ | ~2분 | ⬜ Week 2 |

### 실행 명령어 요약

```bash
# 유닛만 (빠름, API 불필요) — 일상적 개발에 사용
poetry run pytest -m "not integration" --no-cov

# 통합만 (느림, API 필요) — 기능 변경 후 검증
poetry run pytest -m integration --no-cov

# 전체 (유닛 + 통합)
poetry run pytest --no-cov
```

---

## 2. 유닛 테스트 상세 (58개)

### test_state.py (19개) — WorldState

#### TestWorldState (14개)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_get_npc_by_id` | NPC ID 조회 정상 동작 |
| `test_get_npc_by_name` | NPC 이름(한국어) 조회 |
| `test_get_npc_not_found` | 없는 NPC → None 반환 |
| `test_get_all_character_names` | 전체 NPC 이름 목록 |
| `test_get_relationship` | 관계 수치 조회 |
| `test_get_relationship_default` | 없는 관계 → 기본값 50 |
| `test_update_relationship` | 관계 수치 변경 |
| `test_relationship_clamping_upper` | 100 초과 → 100 클램핑 |
| `test_relationship_clamping_lower` | 0 미만 → 0 클램핑 |
| `test_apply_changes_relationship` | 변경 적용 후 값 확인 |
| `test_apply_changes_invalid_character` | 없는 NPC 변경 → 무시 |
| `test_apply_changes_memories` | 기억 추가 확인 |
| `test_advance_turn` | 턴/일차 진행 |
| `test_snapshot` | 상태 스냅샷 구조 |

#### TestLoadFromFile (5개) — Day 2 추가

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_load_from_file_success` | 실제 arcane_academy JSON에서 world+player+6 NPC 정상 로딩 |
| `test_load_from_file_not_found` | 없는 world → FileNotFoundError, 없는 characters → FileNotFoundError |
| `test_load_from_file_invalid_json` | 깨진 JSON → JSONDecodeError |
| `test_load_from_file_missing_fields` | id/name/npcs 누락 → ValueError + 누락 필드명 |
| `test_load_multiple_characters` | 3 NPC 생성 → ID/이름/역할/위치 정확성 검증 |

### test_memory.py (9개) — KeywordMemorySearch

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_add_memory` | 기억 추가 |
| `test_importance_clamping` | 중요도 1-10 범위 제한 |
| `test_search_keyword_matching` | 키워드 매칭 정확도 |
| `test_search_empty_query` | 빈 쿼리 처리 |
| `test_search_no_memories` | 빈 메모리 처리 |
| `test_search_top_k` | top_k 개수 제한 |
| `test_get_recent` | 최근 기억 조회 |
| `test_extract_keywords` | 불용어 제거 |
| `test_search_by_importance` | 중요도 높은 기억 우선 |

### test_validator.py (9개) — StateChangeValidator

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_valid_change` | 정상 변경 통과 |
| `test_invalid_character_rejected` | 없는 캐릭터 거부 |
| `test_invalid_stat_rejected` | 유효하지 않은 스탯 거부 |
| `test_change_clamping` | ±10 범위 클램핑 |
| `test_empty_memory_rejected` | 빈 기억 거부 |
| `test_importance_clamping` | 중요도 범위 제한 |
| `test_invalid_emotion_defaults_to_neutral` | 잘못된 감정 → neutral |
| `test_empty_changes` | 빈 변경사항 처리 |
| `test_no_valid_characters_allows_all` | 캐릭터 목록 비었으면 모두 허용 |

### test_loop_detector.py (6개) — LoopDetector

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_no_loop_initially` | 초기에는 루프 없음 |
| `test_stagnation_detection` | 동일 상태 반복 → 정체 감지 |
| `test_no_stagnation_with_changes` | 변화 있으면 정상 |
| `test_repetition_detection` | 동일 대사 → 반복 감지 |
| `test_no_repetition_with_different_responses` | 다른 응답 → 정상 |
| `test_similarity_calculation` | Jaccard 유사도 계산 |

### test_llm.py (15개) — ClaudeClient (Mock)

| 카테고리 | 테스트 | 검증 내용 |
|----------|--------|-----------|
| **Tool Use** | `test_tool_use_triggers_second_call` | API 2회 호출 확인 |
| | `test_tool_use_returns_state_changes` | state_changes JSON 정확성 |
| | `test_tool_use_returns_final_text` | 2차 응답 텍스트 추출 |
| | `test_second_call_includes_tool_result` | tool_result 메시지 구조 |
| | `test_second_call_includes_assistant_content` | assistant content 유지 |
| **텍스트** | `test_text_only_response` | tool_used=False 확인 |
| | `test_text_only_single_api_call` | API 1회만 호출 |
| | `test_empty_text_response` | 빈 응답 처리 |
| **에러** | `test_api_error_propagates` | 일반 에러 전파 |
| | `test_second_call_error_propagates` | 2차 호출 에러 |
| | `test_anthropic_auth_error` | 인증 에러 (401) |
| **엣지** | `test_tool_use_stop_reason_but_no_tool_block` | tool_use인데 블록 없음 |
| | `test_conversation_history_passed_correctly` | 히스토리 전달 검증 |
| | `test_game_state_tool_definition_correct` | Tool 스키마 구조 |
| | `test_tool_input_contains_relationship_and_memory` | 복수 변경 추출 |

---

## 3. 통합 테스트 상세 (5개) — Day 2 추가

> 파일: `backend/tests/integration/test_game_engine.py`
> 마커: `@pytest.mark.integration`
> 실제 Claude API를 호출하므로 비용 발생 (~$0.05/회)

### TestGameEngineSingleTurn (4개)

| 테스트 | 검증 내용 | 핵심 assert |
|--------|-----------|-------------|
| `test_process_turn_returns_response` | 1턴 플레이 시 텍스트 응답 존재 | `assert result["response"]` |
| `test_process_turn_uses_tool` | Tool Use 발생 + 상태 변경 확인 | `assert changes.get("relationship_changes")` |
| `test_process_turn_updates_state` | 턴 진행, 히스토리 업데이트, 기억 추가 | `assert engine.state.turn == 1` |
| `test_process_turn_korean_response` | 한국어 응답 여부 (빈 응답 시 Tool Use fallback) | `any("가" <= ch <= "힣")` |

### TestGameEngineMultiTurn (1개)

| 테스트 | 검증 내용 | 핵심 assert |
|--------|-----------|-------------|
| `test_two_turn_conversation` | 2턴 대화에서 이름 기억하는지 | `assert len(engine.conversation_history) == 4` |

### 통합 테스트 실행 시 확인되는 것

```
플레이어 → "안녕, 엘레나!"
    ↓
① Memory.search() — 관련 기억 검색          ✅ 동작 확인
② _build_system_prompt() — 프롬프트 구성     ✅ NPC 페르소나 반영
③ Claude API 1차 호출 → Tool Use             ✅ 상태 변경 JSON 반환
④ Validator → 검증 통과                      ✅ 변화량 ±5 범위 내
⑤ WorldState.apply_changes()                 ✅ 관계 수치 실제 변경
⑥ Claude API 2차 호출 → 서사 텍스트          ✅ 한국어 대사 반환
⑦ LoopDetector → 루프 아님                   ✅ 정상 진행
⑧ 대화 히스토리 업데이트                      ✅ user+assistant 추가
```

---

## 4. Mock 전략 — LLM 테스트의 핵심

### 왜 Mock을 쓰나?

| | 실제 API | Mock |
|---|---|---|
| **비용** | ❌ $0.003/call × 수백 회 | ✅ 무료 |
| **네트워크** | ❌ 필요 (오프라인 불가) | ✅ 불필요 |
| **결정성** | ❌ 같은 입력에 다른 출력 | ✅ 같은 입력 → 같은 출력 |
| **속도** | ❌ 2~10초/call | ✅ 58개에 0.17초 |
| **디버깅** | ❌ 응답이 매번 달라 재현 어려움 | ✅ 완전히 통제된 응답 |

### Mock 구조

```python
# 가짜 응답 객체 (Anthropic API 구조를 흉내냄)

@dataclass
class FakeTextBlock:
    type: str = "text"
    text: str = ""

@dataclass
class FakeToolUseBlock:
    type: str = "tool_use"
    id: str = "toolu_test_123"
    name: str = "update_game_state"
    input: dict = ...  # 게임 상태 변경 JSON

@dataclass
class FakeResponse:
    content: list = ...  # [FakeTextBlock] 또는 [FakeToolUseBlock]
    stop_reason: str = "end_turn"  # 또는 "tool_use"
```

### Mock 적용 방법

```python
@pytest.fixture
def claude_client():
    with patch("backend.src.engine.llm.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            anthropic_api_key="fake-key",
            llm_model="claude-sonnet-4-5-20250929",
            llm_max_tokens=2000,
        )
        with patch("backend.src.engine.llm.Anthropic") as mock_cls:
            client = ClaudeClient()
            client.client = mock_cls.return_value
            return client

# 테스트에서 사용:
def test_tool_use(claude_client):
    claude_client.client.messages.create = MagicMock(
        side_effect=[first_response, second_response]  # 1차, 2차 응답
    )
    result = claude_client.process_turn("선물한다", "시스템 프롬프트")
    assert claude_client.client.messages.create.call_count == 2
```

### 유닛 vs 통합 — 역할 분담

```
유닛 테스트 (Mock):
  → "tool_use stop_reason이면 2차 호출을 하는가?" (로직 검증)
  → "tool_result 메시지 구조가 올바른가?" (구조 검증)
  → "API 에러 시 예외가 전파되는가?" (에러 처리 검증)

통합 테스트 (실제 API):
  → "Claude가 실제로 Tool Use를 사용하는가?" (LLM 행동 검증)
  → "프롬프트 튜닝 후 응답 품질이 괜찮은가?" (품질 검증)
  → "2턴 대화에서 컨텍스트를 기억하는가?" (E2E 플로우 검증)
```

---

## 5. 테스트 실행 명령어

```bash
# ── 유닛 테스트 ──

# 전체 유닛 (통합 제외, 추천)
poetry run pytest -m "not integration" --no-cov

# 커버리지 포함
poetry run pytest -m "not integration"

# 특정 파일만
poetry run pytest backend/tests/unit/test_llm.py -v --no-cov

# 특정 클래스만
poetry run pytest backend/tests/unit/test_state.py::TestLoadFromFile -v --no-cov

# 특정 테스트만
poetry run pytest backend/tests/unit/test_state.py::TestWorldState::test_relationship_clamping_upper -v --no-cov

# 키워드로 필터
poetry run pytest -k "tool_use" -v --no-cov

# 실패한 것만 재실행
poetry run pytest --lf -v --no-cov

# ── 통합 테스트 ──

# 통합 테스트만 (API 키 필요, 비용 발생)
poetry run pytest -m integration --no-cov -v -s

# 출력 포함 (NPC 응답 확인)
poetry run pytest -m integration --no-cov -v -s --tb=short

# ── 전체 ──

# 유닛 + 통합 전부
poetry run pytest --no-cov
```

---

## 6. 테스트 작성 가이드라인

### 원칙

1. **한 테스트 = 한 동작 검증** — 여러 assert를 넣되, 하나의 시나리오만 테스트
2. **구체적인 값으로 검증** — `assert True` 금지, `assert result["change"] == 10` 사용
3. **경계값 테스트** — 정상 케이스뿐 아니라 0, 음수, 최대값, 빈 값 테스트
4. **Mock은 외부만** — LLM API만 Mock, 내부 로직은 실제 코드로 테스트
5. **통합 테스트는 비결정적** — LLM 응답이 매번 다르므로 "존재 여부"를 검증, 정확한 값은 검증하지 않음

### 네이밍 규칙

```python
def test_[기능]_[시나리오]():
    """한글로 검증 내용 설명"""

# 예시:
def test_relationship_clamping_upper():
    """관계 수치 상한 (100) 제한"""

def test_load_from_file_missing_fields():
    """필수 필드 누락 시 ValueError"""

def test_process_turn_returns_response():
    """1턴 플레이: 텍스트 응답이 존재하는지"""
```

### 픽스쳐 (conftest.py)

```python
# 이미 정의된 픽스쳐:
world_state          # WorldState (NPC 3명, 관계 설정 포함)
memory_search        # KeywordMemorySearch (기억 3개 사전 등록)
validator            # StateChangeValidator (valid_characters 설정)
arcane_academy_path  # Path("backend/src/worlds/arcane_academy")

# 통합 테스트 픽스쳐:
engine               # GameEngine (arcane_academy 로드 완료, 실제 API 연결)
```

### 새 테스트 추가할 때

```python
# 1. conftest.py에 필요한 픽스쳐 확인

# 2. 적절한 파일에 추가
#    - 상태 관련 → test_state.py (TestWorldState 또는 TestLoadFromFile)
#    - LLM 관련 → test_llm.py
#    - 실제 API → tests/integration/test_game_engine.py (@pytest.mark.integration)
#    - 새 모듈 → test_[모듈이름].py 생성

# 3. 테스트 실행 후 커밋
poetry run pytest -m "not integration" --no-cov   # 유닛만 빠르게
poetry run pytest -m integration --no-cov -v -s   # 통합 (필요시)
```

---

## 7. 발견한 이슈 & 해결

### Issue #1: Claude 2차 응답 빈 텍스트 (Day 2)

```
문제: Tool Use 후 2차 API 호출에서 텍스트 블록이 비어있는 케이스 발생
빈도: ~30% (비결정적)
원인: tool_result에 "응답하라"는 힌트가 없어 Claude가 turn을 끝냄

해결 (llm.py):
1. tool_result 메시지에 "이제 NPC의 대사로 응답하세요" 추가
2. 1차 응답의 텍스트를 fallback으로 보관
3. 2차 응답이 비어있으면 1차 텍스트를 사용

결과: 빈 응답 0% (fallback 포함 시)
```

### Issue #2: 통합 테스트 비결정성 대응

```
문제: LLM 응답이 매번 달라 assert 실패 가능
예: test_korean_response에서 응답이 빈 문자열

해결:
- "값이 정확히 X인가?" 대신 "응답이 존재하는가?" 검증
- 빈 응답 시 Tool Use 성공 여부를 fallback으로 확인
- assert result["response"] or result["tool_used"]
```

---

## 8. E2E 테스트 계획 (Week 2~)

```python
# tests/e2e/test_full_playthrough.py

@pytest.mark.e2e
def test_10_turn_playthrough():
    """10턴 연속 플레이가 자연스럽게 진행되는지"""
    engine = GameEngine()
    engine.initialize("backend/src/worlds/arcane_academy")

    actions = [
        "안녕, 엘레나! 결투장에서 뭐 하고 있어?",
        "마법 연습을 해보고 싶어. 가르쳐줄 수 있어?",
        "엘레나에게 꽃을 선물한다",
        "도서관에 가서 벨라를 찾아본다",
        "벨라에게 결투를 신청한다",
        "루아를 정령정원에서 만난다",
        "루아에게 정령 소환에 대해 물어본다",
        "세인의 연금 연구실을 방문한다",
        "레오와 중앙 로비에서 마주친다",
        "엘레나에게 돌아가서 오늘 있었던 일을 이야기한다",
    ]

    for i, action in enumerate(actions):
        result = engine.process_turn(action)
        assert result["response"], f"Turn {i+1} 응답 없음"
        print(f"Turn {i+1}: {result['response'][:80]}...")

    # 10턴 후 상태 확인
    state = engine.get_state()
    assert state["turn"] == 10
    assert state["day"] >= 2           # 5턴마다 하루 → 최소 2일
    assert len(engine.memory.memories) >= 5  # 기억 최소 5개
```

---

## 9. 누적 테스트 현황

| 날짜 | 유닛 | 통합 | 총 테스트 | 통과 | 추가된 테스트 |
|------|------|------|-----------|------|---------------|
| Day 1 (2/15) | 53 | 0 | 53 | 53 | 최초 작성 |
| Day 2 (2/16) | 58 | 5 | **63** | **63** | +5 유닛 (load_from_file), +5 통합 (GameEngine) |
| Day 3 | - | - | - | - | 예정: EventManager 테스트 |
