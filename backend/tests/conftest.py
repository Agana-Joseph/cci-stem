"""Pytest fixtures providing isolated database, seeded reference data, and TestClient."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.rate_limiter import rate_limiter
from app.database.base import Base
from app.database.seed import seed_reference_data
from app.database.session import get_db
from app.main import create_app
import app.models  # noqa: F401


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSessionLocal()
    seed_reference_data(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, tmp_path: Path) -> Generator[TestClient, None, None]:
    rate_limiter.reset()
    settings = get_settings()
    settings.reports_storage_dir = tmp_path / "reports"
    settings.rate_limit_enabled = True
    settings.rate_limit_lookup_per_minute = 15

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {
        "X-API-Key": get_settings().admin_api_key,
        "X-Actor-Id": "test-admin",
    }
