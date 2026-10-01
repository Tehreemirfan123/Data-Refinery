"""Shared pytest fixtures."""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session
from backend.app.db.session import engine


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Database session wrapped in a transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()