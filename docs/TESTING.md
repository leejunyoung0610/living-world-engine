# Living World Engine - 테스트 전략

> "테스트가 없으면 리팩토링도, 배포도, 자신감도 없다."

---

## 1. 테스트 피라미드

```
        ╱  E2E  ╲           ← 전체 게임 플로우 (10턴 플레이)
       ╱─────────╲          
      ╱ Integration╲        ← LLM + State + Memory 연동
     ╱───────────────╲      
    ╱   Unit Tests    ╲     ← 각 모듈 독립 검증 (53개)
   ╱───────────────────╲    
```

| 레벨 | 파일 수 | 테스트 수 | API 필요 | 실행 시간 |
|------|---------|-----------|----------|-----------|
| **Unit** | 5개 | 53개 | ❌ (Mock) | ~0.14초 |
| **Integration** | 예정 | 예정 | ✅ | ~30초 |
| **E2E** | 예정 | 예정 | ✅ | ~2분 |

---

## 2. 현재 유닛 테스트 상세

### test_state.py (14개) — WorldState

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

## 3. Mock 전략 — LLM 테스트의 핵심

### 왜 Mock을 쓰나?

```
실제 API 호출:
  ❌ 비용 발생 ($0.003/call × 수백 회 = $$$)
  ❌ 네트워크 의존 (오프라인 테스트 불가)
  ❌ 비결정적 (같은 입력에 다른 출력)
  ❌ 느림 (call당 2-5초)

Mock 테스트:
  ✅ 무료
  ✅ 오프라인 가능
  ✅ 결정적 (같은 입력 → 같은 출력)
  ✅ 빠름 (53개 0.14초)
```

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

---

## 4. 테스트 실행 방법

```bash
# 전체 유닛 테스트 (추천)
poetry run pytest backend/tests/unit/ -v --no-cov

# 커버리지 포함
poetry run pytest backend/tests/unit/ -v

# 특정 파일만
poetry run pytest backend/tests/unit/test_llm.py -v --no-cov

# 특정 테스트만
poetry run pytest backend/tests/unit/test_state.py::TestWorldState::test_relationship_clamping_upper -v --no-cov

# 키워드로 필터
poetry run pytest -k "tool_use" -v --no-cov

# 실패한 것만 재실행
poetry run pytest --lf -v --no-cov
```

---

## 5. 테스트 작성 가이드라인

### 원칙

1. **한 테스트 = 한 동작 검증** — 여러 assert를 넣되, 하나의 시나리오만 테스트
2. **구체적인 값으로 검증** — `assert True` 금지, `assert result["change"] == 10` 사용
3. **경계값 테스트** — 정상 케이스뿐 아니라 0, 음수, 최대값, 빈 값 테스트
4. **Mock은 외부만** — LLM API만 Mock, 내부 로직은 실제 코드로 테스트

### 네이밍 규칙

```python
def test_[기능]_[시나리오]_[기대결과]():
    """한글로 검증 내용 설명"""

# 예시:
def test_relationship_clamping_upper():
    """관계 수치 상한 (100) 제한"""

def test_invalid_character_rejected():
    """존재하지 않는 캐릭터 변경 거부"""
```

### 새 테스트 추가할 때

```python
# 1. conftest.py에 필요한 픽스쳐 확인
#    world_state, memory_search, validator 등 이미 정의되어 있음

# 2. 적절한 파일에 추가
#    - 상태 관련 → test_state.py
#    - LLM 관련 → test_llm.py
#    - 새 모듈 → test_[모듈이름].py 생성

# 3. 테스트 실행 후 커밋
poetry run pytest -v --no-cov
```

---

## 6. 통합 테스트 계획 (Week 2~)

### 예정 테스트

```python
# tests/integration/test_game_flow.py

@pytest.mark.slow  # 실제 API 호출
async def test_single_turn_with_tool_use():
    """1턴 플레이에서 상태가 실제로 변경되는지"""
    engine = GameEngine()
    engine.initialize("backend/src/worlds/arcane_academy/...")
    result = engine.process_turn("엘레나에게 꽃을 선물한다")
    
    assert result["response"]              # 서사 텍스트 있음
    assert result["tool_used"]             # Tool Use 발생
    assert result["state_changes"]         # 상태 변경 있음

@pytest.mark.slow
async def test_10_turn_playthrough():
    """10턴 연속 플레이가 자연스럽게 진행되는지"""
    engine = GameEngine()
    engine.initialize(...)
    
    for i, action in enumerate(TEN_TURN_ACTIONS):
        result = engine.process_turn(action)
        assert result["response"], f"Turn {i} failed"
        assert not result.get("error")
    
    # 10턴 후 상태 확인
    state = engine.get_state()
    assert state["turn"] == 10
    assert state["day"] > 1
    assert len(engine.memory.memories) > 5
```

---

## 7. 누적 테스트 현황

| 날짜 | 총 테스트 | 통과 | 실패 | 추가된 테스트 |
|------|-----------|------|------|---------------|
| Day 1 (2/15) | 53 | 53 | 0 | 최초 작성 |
| Day 2 | - | - | - | - |
| ... | ... | ... | ... | ... |
