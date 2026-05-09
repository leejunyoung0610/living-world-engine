"""slowapi 인스턴스 — 라우트에서 `@limiter.limit(...)` 공유."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# `create_app` 에서 `enabled` 를 설정값에 맞게 조정한다.
limiter = Limiter(key_func=get_remote_address)
