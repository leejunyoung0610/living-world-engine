"""공용 컬럼 타입·변환 헬퍼."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Numeric

#: 금액(USD) — 고정 소수. 최대 999,999.999999, 1e-6 USD 단위 (마이그레이션 0016).
MONEY_SCALE = 6
MONEY = Numeric(precision=12, scale=MONEY_SCALE, asdecimal=True)

_QUANT = Decimal(1).scaleb(-MONEY_SCALE)


def to_money(value: float | int | str | Decimal) -> Decimal:
    """금액을 컬럼 스케일(소수 6자리)의 ``Decimal`` 로 변환.

    float 는 ``str()`` 을 거쳐 이진 오차가 그대로 Decimal 로 옮겨지지 않게 한다.
    """
    if isinstance(value, Decimal):
        d = value
    else:
        d = Decimal(str(value))
    return d.quantize(_QUANT, rounding=ROUND_HALF_UP)
