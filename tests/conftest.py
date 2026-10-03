"""Shared pytest fixtures.

Tests run against a separate database (TEST_DATABASE_URL), so they never see
or modify development/demo data. Each database test runs inside a transaction
that is rolled back afterwards. Tests that do not use the database never
connect to it.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import backend.app.models  # noqa: F401  (registers all models with Base.metadata)
from backend.app.core.config import get_settings
from backend.app.db.base import Base


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Engine for the isolated test database; tables created once per run."""
    settings = get_settings()
    if not settings.test_database_url:
        pytest.fail("TEST_DATABASE_URL is not set. Add it to your .env file.")
    if settings.test_database_url == settings.database_url:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL.")

    engine = create_engine(settings.test_database_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Test-database session wrapped in a transaction that is always rolled back."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()