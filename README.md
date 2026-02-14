# Living World Engine

> AI 기반 동적 세계 시뮬레이션 RPG 엔진

Character.AI와 Replika의 한계를 넘어서는 차세대 대화형 게임 엔진입니다.

## 핵심 기능

| 기존 챗봇의 문제 | Living World의 해결책 |
|---|---|
| 장기 기억 부족 | 키워드 기반 메모리 검색 + 중요도 관리 |
| 초기 프롬프트 루프 | 동적 성격 변화 + 경험 기반 성장 |
| 새 이벤트 없음 | 조건 기반 이벤트 + LLM 즉석 생성 |
| 상태 변화 없음 | Tool Use 기반 자동 상태 관리 |

## 기술 스택

- **Backend**: Python 3.11+, FastAPI
- **AI**: Anthropic Claude API (Sonnet 4.5) - Tool Use 직접 구현
- **Frontend**: React (예정)
- **의존성 관리**: Poetry

## 빠른 시작

```bash
# 1. 의존성 설치
poetry install

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력

# 3. API 키 테스트
poetry run python backend/scripts/test_claude_api.py

# 4. 서버 실행 (Week 3~)
poetry run uvicorn backend.src.main:app --reload
```

## 프로젝트 구조

```
living-world-engine/
├── pyproject.toml              # 의존성 (Poetry)
├── .env.example                # 환경 변수 템플릿
├── backend/
│   ├── src/
│   │   ├── engine/             # 핵심 게임 엔진
│   │   │   ├── state.py        # 상태 관리 (WorldState)
│   │   │   ├── memory.py       # 메모리 시스템
│   │   │   ├── llm.py          # Claude API 통합
│   │   │   ├── validator.py    # 상태 변경 검증
│   │   │   ├── loop_detector.py# 루프 감지
│   │   │   └── game_loop.py    # 메인 게임 루프
│   │   ├── api/                # REST API (FastAPI)
│   │   ├── worlds/             # 세계관 데이터
│   │   └── utils/              # 유틸리티
│   ├── tests/                  # 테스트
│   └── scripts/                # 개발 스크립트
├── frontend/                   # React UI (Week 4)
└── docs/                       # 문서
```

## 개발 일정

| 주차 | 목표 | 상태 |
|------|------|------|
| Week 1 (2/15~) | 핵심 엔진 + LLM 통합 | 진행중 |
| Week 2 | 이벤트 + 루프 방지 | 예정 |
| Week 3 | 세계관 + API | 예정 |
| Week 4 | UI + 문서 + 데모 | 예정 |

## 라이선스

학교 과제 + 포트폴리오 프로젝트
