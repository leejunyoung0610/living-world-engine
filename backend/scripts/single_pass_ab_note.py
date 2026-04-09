#!/usr/bin/env python3
"""Phase 1.5 Single-Pass Tool Use — 수동 A/B 안내

실제 20턴 비교는 API 키가 필요하므로 ``play_game`` 등으로 수동 실행한다.

로그( INFO )에서 확인:
  - ``✅ Single-Pass (1회 호출, 툴+대사 동시)``
  - ``⚠️ Tool Use → 2차 호출 (Fallback)``
  - ``📡 LLM API 호출 수: N회``

턴 결과 dict에 ``llm_api_calls`` (1 또는 2) 포함.

롤백 / A/B:
  - 프로젝트 루트 ``.env`` 에 ``ENABLE_SINGLE_PASS=false`` (기본은 ``true``)
  - 또는 ``backend/src/utils/config.py`` 의 ``enable_single_pass`` 기본값 변경
"""

if __name__ == "__main__":
    print(__doc__)
