#!/usr/bin/env python3
"""
Haiku API 연결 스모크 테스트 (기본은 항상 Haiku — .env 의 LLM_MODEL 과 무관).

.env 에 Sonnet 이 있어도 이 스크립트는 기본적으로 Haiku 만 호출합니다.
게임/설정과 동일한 모델로 테스트하려면:
  poetry run python backend/haiku_test.py --from-env

❌ command not found: python → poetry run python … 또는 python3 사용

권장:
  cd /Users/leejy/Desktop/engine && poetry run python backend/haiku_test.py
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

# Poetry가 시스템 3.9 경로의 urllib3를 먼저 건드릴 때 나는 LibreSSL 경고 숨김 (실행은 3.11)
try:
    from urllib3.exceptions import NotOpenSSLWarning

    warnings.simplefilter("ignore", NotOpenSSLWarning)
except ImportError:
    pass

from dotenv import load_dotenv
from anthropic import Anthropic

# engine/.env 로드 (이 파일이 backend/ 에 있으므로 상위가 루트)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

_DEFAULT_HAIKU = "claude-haiku-4-5-20251001"

_ALIASES = {
    "haiku": _DEFAULT_HAIKU,
    "hikaru": _DEFAULT_HAIKU,
    "sonnet": "claude-sonnet-4-5-20250929",
    "sonnet45": "claude-sonnet-4-5-20250929",
    "haiku45": _DEFAULT_HAIKU,
}


def _resolve_model(raw: str) -> str:
    k = raw.strip().lower()
    return _ALIASES.get(k, raw.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Haiku API 스모크 테스트")
    parser.add_argument(
        "--from-env",
        action="store_true",
        help=".env 의 LLM_MODEL(또는 별칭)을 그대로 사용 (Sonnet 테스트용)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 없음 — engine/.env 를 확인하세요.")
        return 1

    if args.from_env:
        raw = os.environ.get("LLM_MODEL", _DEFAULT_HAIKU)
        model = _resolve_model(raw)
        source = "LLM_MODEL (.env)"
    else:
        model = _DEFAULT_HAIKU
        source = "고정 Haiku (haiku_test 기본)"

    print(f"🧠 모델: {model}  ({source})")
    try:
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=80,
            messages=[{"role": "user", "content": "한 줄로만 답해: 연결 OK?"}],
        )
        text = msg.content[0].text
        print(f"✅ 응답: {text}")
    except Exception as e:
        print(f"❌ 실패: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
