"""SQLAlchemy engine and request-session ownership."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by models and Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """Own one SQLAlchemy engine and short-lived request sessions."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        if not url:
            raise ValueError("database url must not be empty")
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            engine_options.update(
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            engine_options.update(
                pool_size=5,
                max_overflow=5,
                pool_recycle=1800,
                pool_timeout=10,
            )
        self.engine: Engine = create_engine(url, echo=echo, **engine_options)
        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transaction-capable session and always close it."""
        value = self._session_factory()
        try:
            yield value
        finally:
            value.close()

    def dispose(self) -> None:
        """Release pooled connections."""
        self.engine.dispose()
