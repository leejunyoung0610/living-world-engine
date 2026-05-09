"""CORS·보안 헬퍼 단위 테스트."""

from __future__ import annotations

import pytest

from backend.src.api.security import validate_cors_origins_for_production


def test_cors_star_rejected_in_production_mode() -> None:
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_cors_origins_for_production(debug=False, origins=["https://a.com", "*"])


def test_cors_star_allowed_in_debug() -> None:
    validate_cors_origins_for_production(debug=True, origins=["*"])
