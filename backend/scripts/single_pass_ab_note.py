#!/usr/bin/env python3
"""Phase 1.5 Single-Pass Tool Use — 수동 A/B 안내

실제 20턴 비교는 API 키가 필요하므로 ``play_game`` 등으로 수동 실행한다.

로그( INFO )에서 확인:
  - ``✅ Single-Pass (1회 호출, 툴+대사 동시)``
  - ``⚠️ Tool Use → 2차 호출 (Fallback)``
  - ``📡 LLM API 호출 수: N회``

턴 결과 dict에 ``llm_api_calls`` (1 또는 2) 포함.

롤백:
  - ``game_loop.py`` 의 ``process_turn(..., enable_single_pass=True)`` 를 ``False`` 로 변경
  - 또는 환경 변수/설정으로 분기 추가 (미구현 시 위 한 줄 수정)
"""

if __name__ == "__main__":
    print(__doc__)
