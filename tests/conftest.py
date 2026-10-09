import os

# Tests use the test environment (app/configs/.env_test). Environment variables
# take priority over env files, and this runs before the app is imported.
os.environ["APP_ENV"] = "TEST"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402, F401
from app.db import Base  # noqa: E402
from app.keitaro import HttpKeitaroClient  # noqa: E402
from tests.keitaro_service.app import create_app  # noqa: E402
from tests.keitaro_service.store import KeitaroStore  # noqa: E402

FAKE_KEITARO_URL = "http://keitaro.test"
FAKE_KEITARO_KEY = "test-api-key"

# In-memory SQLite by default; set TEST_DATABASE_URL to run the tests on PostgreSQL.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def engine():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def keitaro_store():
    """State of the fake Keitaro: the test data from seed_test_data.py, in memory."""
    return KeitaroStore(None)


@pytest.fixture
def keitaro(keitaro_store):
    """The production HTTP client talking to the fake Keitaro service in-process."""
    service = create_app(store=keitaro_store, api_key=FAKE_KEITARO_KEY)
    http = TestClient(
        service,
        base_url=f"{FAKE_KEITARO_URL}/admin_api/v1",
        headers={"Api-Key": FAKE_KEITARO_KEY, "Accept": "application/json"},
    )
    return HttpKeitaroClient(FAKE_KEITARO_URL, FAKE_KEITARO_KEY, http_client=http)
