# 비용 최적화 계획

## 현재 상태 (Day 6)

### 비용 분석
- Turn당: $0.036
- 하루 10턴: $10.8/월
- 하루 50턴: $54/월

### 토큰 분석
```
System Prompt: 992 tokens
Tools Definition: 274 tokens
API Overhead: 3.7x multiplier

1차 호출: 4,658 tokens
2차 호출: 4,968 tokens
총: 9,626 tokens
```

### 원인
- API 내부 포맷팅: 3.7배 오버헤드 (불가피)
- System Prompt: 최적화 가능
- Tool Use 2단계: 구조적 한계

---

## Week 2 최적화 (Day 7-12)

### Day 7 - System Prompt 압축
**목표:** 17% 비용 절감

**작업:**
1. SystemPromptOptimizer 클래스 구현
2. NPC 프로필 간소화 (1434 → 600 chars)
3. 응답 규칙 압축
4. 중요 기억만 포함 (importance >= 6)

**예상 효과:**
- 992 → 500 tokens
- $0.036 → $0.030/turn

**파일:**
- `backend/src/engine/prompt_optimizer.py` (신규)
- `backend/src/engine/game_loop.py` (수정)

---

### Day 8 - Prompt Caching
**목표:** 58% 비용 절감 (누적)

**작업:**
1. Anthropic API Prompt Caching 적용
2. System prompt를 캐싱 가능한 형태로 변경
3. 5분간 재사용 (90% 할인)

**예상 효과:**
- System prompt 비용: 90% 감소
- $0.030 → $0.015/turn

**파일:**
- `backend/src/engine/llm.py` (수정)

---

### Day 9 - 안정성 개선
**목표:** 최적화 품질 검증

**작업:**
1. PerformanceMonitor 구현
2. 병목 지점 파악
3. 에러 처리 강화
4. 품질 확인 (9/10 유지?)

---

### Day 10-11 - 장기 기억 시스템
**최적화 없음, 기능 개발**

**작업:**
1. LongTermMemory 클래스
2. 자동 태깅
3. 중요도 기반 검색

---

### Day 12 - Week 2 회고
**목표 검증:**
- 비용: $0.015/turn ✓
- 품질: 9/10 ✓
- 기능: 장기 기억 ✓

---

## Week 3 최적화 (Day 13-19)

### Day 13-14 - PostgreSQL
**최적화 아님, 확장성**

### Day 15 - Model Switching
**목표:** 83% 비용 절감 (최종)

**작업:**
1. ModelSelector 구현
2. 중요 대화: Sonnet (30%)
3. 일반 대화: Haiku (70%)

**예상 효과:**
- $0.015 → $0.006/turn
- 품질: 8-9/10 유지

---

## 최종 목표

### 비용
```
현재: $0.036/turn
Week 2: $0.015/turn (58% ↓)
Week 3: $0.006/turn (83% ↓)
```

### 품질
```
현재: 9/10
목표: 8-9/10 유지
```

### 경쟁력
```
Replika: $5.83/월 vs 우리: $1.8-9/월 ✅
품질: 우리가 2점 높음 ✅
```