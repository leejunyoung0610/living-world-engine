# Living World Engine — 지원·포트폴리오용 요약

> README의 기술 설명을 보완하는 **자기소개서·이력서·지원 폼**용 짧은 문단 모음입니다. 숫자(비용·테스트 개수)는 실제 측정값으로 갱신하세요.

---

## 프로젝트 한 줄

**Anthropic Claude Tool Use를 직접 연동한 대화형 RPG 엔진**으로, NPC 대사와 게임 상태(관계·장기 기억)를 구조화된 툴 출력으로 동기화하고, 프롬프트 캐싱·Single-Pass 호출로 API 비용과 지연을 줄였습니다.

---

## 본인 역할 (예시 — 본인 상황에 맞게 수정)

- 게임 루프·상태·검증·LLM 클라이언트 설계 및 구현
- 시스템 프롬프트 static/dynamic 분리 및 Anthropic 프롬프트 캐시 적용
- Tool Use 2단 호출 + **1차 응답에 대사가 있을 때 2차 스킵**하는 Single-Pass 로직
- Usage 기반 턴 비용·캐시 통계 로깅
- pytest(Mock LLM) 기반 유닛 테스트 유지

---

## 사용 기술 (키워드)

`Python 3.11` · `Anthropic API` · `Tool Use` · `FastAPI` · `Poetry` · `pytest` · `Pydantic` · REST API 설계(예정) · 프롬프트 엔지니어링 · 비용 최적화

---

## 성과·수치 (채워 넣기)

- 유닛 테스트: `poetry run pytest backend/tests/unit` 기준 **N개 통과** (실행 후 기입)
- 세션 예시: 턴당 평균 비용 **약 $0.0X** (세션·모델·프롬프트에 따라 변동)
- Single-Pass 적용 후 **LLM API 호출 수 감소** (로그 `llm_api_calls`·`✅ Single-Pass` 빈도로 확인)

---

## 트레이드오프·한계 (면접 대비)

- **LangChain 미사용:** 디버깅·제어는 쉬우나 보일러플레이는 직접 유지
- **장기 기억:** 현재 JSON 파일 기반 — 확장 시 DB 마이그레이션 필요
- **프론트·배포:** 미완 — **개발 중** 명시
- **툴 미호출 턴:** `new_memories`가 비면 해당 턴은 장기기억 스토어에 추가 없음

---

## 앞으로 할 일 (지원서 ‘계획’란용)

- 웹 UI 및 세션 관리
- API 안정화·문서화(OpenAPI)
- 스트리밍·재시도·관측성(로그/메트릭)
- 기억 저장소 고도화

---

## 저장소·데모

- GitHub / 배포 URL: *(추가 시 기입)*
- 데모 영상: *(선택)*
