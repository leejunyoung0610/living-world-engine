"""경쟁 조건 없는 카운터·집계 갱신 헬퍼 (PostgreSQL · SQLite).

일·월 집계 행은 "없으면 만들고, 있으면 DB 안에서 더한다"로 다룬다:

1. ``insert_ignore`` — PK 충돌이면 아무것도 하지 않는 INSERT (동시 요청이 둘 다 행을 만들려 해도 안전)
2. ``UPDATE ... SET col = col + :delta [WHERE 조건]`` — 읽고-더하고-쓰기를 DB 한 문장으로

ORM 세션 동기화(``synchronize_session``)는 끈다. 'fetch'/'auto' 는 SET 식을 메모리의
(오래됐을 수 있는) 객체에 파이썬으로 다시 적용해 값이 어긋날 수 있다. 갱신 후 값이 필요하면
``select(Model.col)`` 처럼 컬럼 단위로 다시 읽는다(항상 DB 값).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert as generic_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

#: ORM-enabled UPDATE 에 붙이는 실행 옵션 — 세션 내 객체를 건드리지 않는다.
NO_SYNC = {"synchronize_session": False}


def insert_ignore(db: Session, model: type[Any], values: dict[str, Any]) -> None:
    """PK 가 이미 있으면 무시하는 INSERT.

    PostgreSQL·SQLite 는 ``INSERT ... ON CONFLICT DO NOTHING`` 한 문장.
    그 외 방언은 SAVEPOINT 안에서 INSERT 후 무결성 오류를 삼킨다.
    """
    table = model.__table__
    pk_cols = [c.name for c in table.primary_key.columns]
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        db.execute(pg_insert(table).values(**values).on_conflict_do_nothing(index_elements=pk_cols))
        return
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        db.execute(
            sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=pk_cols)
        )
        return
    try:
        with db.begin_nested():
            db.execute(generic_insert(table).values(**values))
    except IntegrityError:
        pass
