"""slowapi 인스턴스 — 라우트에서 `@limiter.limit(...)` 공유.

사용 순서 (slowapi 규약)::

    @router.post("/path")          # 라우트 데코레이터가 가장 바깥
    @limiter.limit("30/minute")    # 리미터는 함수 바로 위
    def endpoint(request: Request, ...): ...

반대 순서면 라우터가 래핑 전 함수를 등록하므로 한도가 전혀 적용되지 않는다.
"""

from __future__ import annotations

import typing
from collections.abc import Callable
from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address


class _AnnotationSafeLimiter(Limiter):
    """`from __future__ import annotations` 를 쓰는 라우트 모듈과 호환되는 Limiter.

    FastAPI 는 엔드포인트의 문자열 어노테이션을 **호출 객체의 ``__globals__``** 로 평가한다.
    slowapi 래퍼의 ``__globals__`` 는 slowapi 모듈이라 ``TurnBody`` 같은 이름을 찾지 못하고,
    본문 파라미터가 쿼리 파라미터로 잘못 해석된다(422). 래핑 전에 원 함수 모듈 기준으로
    어노테이션을 실제 타입으로 해석해 둔다.
    """

    def limit(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        inner = super().limit(*args, **kwargs)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            func.__annotations__ = typing.get_type_hints(func, include_extras=True)
            return inner(func)

        return decorator


# `create_app` 에서 `enabled` 를 설정값에 맞게 조정한다.
limiter = _AnnotationSafeLimiter(key_func=get_remote_address)
