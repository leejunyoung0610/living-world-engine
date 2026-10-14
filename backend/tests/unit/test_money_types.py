"""금액 컬럼 타입 (마이그레이션 0016) · to_money 변환."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import Float, Numeric

from backend.src.db.models import ImageGenCostDaily, PlatformCostDaily
from backend.src.db.types import to_money


@pytest.mark.parametrize("model", [PlatformCostDaily, ImageGenCostDaily])
def test_cost_usd_is_fixed_point_numeric(model) -> None:
    col_type = model.__table__.c.cost_usd.type
    assert isinstance(col_type, Numeric)
    assert not isinstance(col_type, Float)
    assert (col_type.precision, col_type.scale) == (12, 6)
    assert col_type.asdecimal is True


def test_to_money_quantizes_to_six_places() -> None:
    assert to_money(0.1) + to_money(0.2) == Decimal("0.3")  # float 이면 0.30000000000000004
    assert to_money(0.0123456789) == Decimal("0.012346")
    assert to_money("1.5") == Decimal("1.500000")
    assert to_money(Decimal("2")) == Decimal("2.000000")
    assert to_money(0) == Decimal("0")
