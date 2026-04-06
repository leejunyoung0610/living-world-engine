# Living World Engine

> **AI 기반 동적 세계 시뮬레이션 RPG 엔진** — Anthropic Claude Tool Use로 NPC 대화·관계·장기 기억을 구조화해 관리합니다.

[![Status](https://img.shields.io/badge/status-in%20development-yellow)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![Tests](https://img.shields.io/badge/tests-pytest-success)]()

**포트폴리오·기업/부트캠프 지원용 개인 프로젝트**입니다. 핵심 루프와 비용 최적화는 동작하며, **UI·배포·상용화는 진행 중**입니다.

---

## ⚠️ 현재 상태 (개발 중)

| 구분 | 상태 |
|------|------|
| 게임 엔진 · CLI 플레이 (`play_game`) | ✅ 동작 |
| Claude Tool Use · 상태 검증 · 장기 기억 | ✅ 동작 |
| 프롬프트 캐시 분리 · Single-Pass 툴 경로 | ✅ 적용 |
| FastAPI 서버 | 부분 / 확장 예정 |
| React 프론트 | 미구현 (예정) |
| 프로덕션 배포 · 인증 | 미구현 |

**UGC 플랫폼 MVP(베타) 계획**은 [`docs/UGC_MVP_PLAN.md`](docs/UGC_MVP_PLAN.md)에 통합해 두었다. (정책 상한 vs 1차 초대 인원, 4주 범위, 비용·배포 원칙)

새 기능·리팩터는 **테스트(`pytest`)와 함께** 추가하는 것을 원칙으로 합니다.

---

## 지원·포트폴리오용 한 줄 요약

**“LangChain 없이 Anthropic Messages API로 Tool Use 2단(필요 시 1단) 파이프라인을 직접 구현하고, 시스템 프롬프트 캐시·턴 비용 추적으로 운영 비용을 줄인 대화형 게임 엔진.”**

- 지원서/자소서에 붙이기 좋은 **역할·성과·기술 스택 요약**은 [`docs/PORTFOLIO.md`](docs/PORTFOLIO.md)를 참고하세요.

---

## 최근에 반영한 개선 (요약)

- **프롬프트 캐시(Phase 1):** 시스템 프롬프트를 `static` / `dynamic` 블록으로 분리, Anthropic 프롬프트 캐시가 static에만 적용되도록 구성.
- **Single-Pass Tool Use (Phase 1.5):** 1차 응답에 NPC 대사(text)와 `tool_use`가 함께 있으면 **2차 API 호출 생략** → 지연·비용 절감 (텍스트 없을 때만 기존 2차 폴백).
- **Usage / 비용:** API `usage` 기반 턴 비용·캐시 read/write 로깅, 캐시 할인 반영 추정.
- **컨텍스트 (Phase 2):** `ContextManager` — 예산 `MAX_CONTEXT_TOKENS=1600`, 최근 3턴 + NPC 샘플링 1턴/윈도 20턴, 초과 시 Layer2→Layer1 순 축소. 2차 LLM 호출 히스토리 길이는 Layer1과 동기화.
- **장기 기억:** `LongTermMemory` — 중요도·검색 기반.

---

## 핵심 기능 (설계 의도)

| 기존 챗봇의 한계 | 이 프로젝트의 접근 |
|------------------|-------------------|
| 장기 기억 부족 | JSON 기반 `LongTermMemory` + 중요도·태그·쿼리 관련도 검색 |
| 상태가 텍스트에만 존재 | `update_game_state` Tool → 검증 후 `WorldState`·기억 반영 |
| 비용·지연 | Static/Dynamic 캐시 + Single-Pass(조건부) + 컨텍스트 상한 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Runtime | Python 3.11+ |
| LLM | Anthropic Claude (Sonnet 4.5 등), **Tool Use 직접 연동** (LangChain 미사용) |
| API | FastAPI (확장 예정) |
| 테스트 | pytest, Mock 기반 LLM 유닛 테스트 |
| 의존성 | Poetry |

---

## 아키텍처 하이라이트

1. **`GameEngine.process_turn`:** 메모리 검색 → 시스템 블록(static/dynamic) → `ClaudeClient.process_turn` → 사용량 기록 → `StateChangeValidator` → 상태·장기기억 반영.
2. **`llm.py`:** `stop_reason == tool_use` 시 `tool_use.input`을 `state_changes`로 사용; Single-Pass 시 1차 텍스트가 있으면 2차 생략.
3. **`prompt_optimizer.py`:** 세계관·규칙·툴 지침은 static, 장소·NPC·기억은 dynamic.

---

## 비용 목표까지의 거리 (추정)

측정 조건(세션·모델·프롬프트)에 따라 변동합니다. 아래는 **한 세션 기준 참고치**입니다.

| 항목 | 값 |
|------|-----|
| **현재 (참고)** | ~$0.013 / turn |
| **목표** | ~$0.002 / turn |
| **추가 필요 절감** | 약 **84%** (목표 대비) |

**남은 최적화 (로드맵과 연계)**

| Phase | 내용 |
|-------|------|
| **Phase 1** | 프롬프트 캐시 분리(static/dynamic) — 적용됨 |
| **Phase 1.5** | Single-Pass Tool Use — 적용됨 |
| **Phase 2** | Context 관리 — 예산 1600tok, Layer1 3턴, Layer2 NPC당 1턴·윈도 20턴, 예산 초과 시 단계적 축소 (**적용됨**) |
| **Phase 3** | Output 제한 — 기본 `LLM_MAX_TOKENS=768` (`.env`), 필요 시 조정 |
| **Phase 4** | DialogueRouter 등 **선택적 경량 모델** (미구현 가능, 품질·검증 비용 고려) |

> **참고:** $0.002/턴은 Sonnet 단일 모델·현재 툴 스키마를 유지한 채로는 **매우 공격적인 목표**일 수 있습니다. 달성에는 **입력 토큰 대폭 절감**, **캐시 적중 극대화**, 또는 **일부 턴의 모델 다운그레이드** 등이 겹쳐야 할 수 있으며, 그때마다 **품질 회귀 테스트**가 필요합니다.

---

## 추가 구현 계획 (로드맵)

우선순위는 실제 일정에 따라 바뀔 수 있습니다.

| 단계 | 내용 |
|------|------|
| 단기 | FastAPI 엔드포인트 정리, 세션·환경 설정 분리, `enable_single_pass` 설정 파일화 |
| 중기 | React(또는 단일 페이지) UI, 스트리밍 응답 검토, 통합 테스트 보강 |
| 중기 | 루프 감지 재활성화·튜닝, 이벤트 시스템 고도화 |
| 장기 | 기억 저장소 PostgreSQL 등 마이그레이션, 멀티 유저·관측(로그/메트릭) |

---

## 빠른 시작

```bash
# 의존성
poetry install

# 환경 변수
cp .env.example .env
# ANTHROPIC_API_KEY 설정

# Claude 연결 스모크 테스트
poetry run python backend/scripts/test_claude_api.py

# 터미널에서 플레이 (세계관 경로는 프로젝트에 맞게)
poetry run python -m backend.play_game

# 유닛 테스트 (통합 테스트는 API 키·마커 필요할 수 있음)
poetry run pytest backend/tests/unit -q --no-cov

# 참고: 장기 기억은 실행 시 `data/memories.json`에 생성됩니다(저장소에는 포함하지 않음).

# API 서버 (구성에 따라)
poetry run uvicorn backend.src.main:app --reload
```

---

## 프로젝트 구조 (요약)

```
engine/
├── pyproject.toml
├── README.md
├── DEVELOPMENT.md              # 개발 일지·의사결정
├── docs/
│   ├── PORTFOLIO.md            # 지원서용 요약
│   ├── UGC_MVP_PLAN.md         # UGC 베타 MVP 기획 (통합본)
│   └── …
├── backend/
│   ├── src/
│   │   ├── engine/
│   │   │   ├── game_loop.py    # 메인 루프
│   │   │   ├── llm.py          # Claude + Tool Use + Single-Pass
│   │   │   ├── prompt_optimizer.py
│   │   │   ├── state.py
│   │   │   ├── validator.py
│   │   │   ├── long_term_memory.py
│   │   │   ├── context_manager.py
│   │   │   ├── events.py
│   │   │   └── loop_detector.py
│   │   ├── api/
│   │   ├── utils/              # config, logger, usage_tracker …
│   │   └── worlds/
│   ├── tests/
│   ├── scripts/
│   └── play_game.py
└── frontend/                   # 예정
```

---

## 문서

| 파일 | 설명 |
|------|------|
| [docs/UGC_MVP_PLAN.md](docs/UGC_MVP_PLAN.md) | **UGC MVP·베타** 기획 통합본 (범위·주차·비용·배포·체크리스트) |
| [docs/PORTFOLIO.md](docs/PORTFOLIO.md) | 기업·부트캠프 지원용 요약 (복붙용) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 일자별 개발 기록 · 코드 기준 최적화 스냅샷 |

---

## 라이선스 · 문의

개인 학습 및 **포트폴리오 목적** 프로젝트입니다. 상업적 이용 시 별도 정리가 필요할 수 있습니다.
